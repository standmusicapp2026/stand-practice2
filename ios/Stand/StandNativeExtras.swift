// StandNativeExtras.swift
// The direct link between the iPad and the iPhone apps (MultipeerConnectivity: the way AirDrop finds
// devices — same Wi-Fi, or just nearby over Apple's peer-to-peer Wi-Fi; no internet, no codes).
// Everything the camera link and the practice sharing need goes through it:
//   • small messages (JSON strings), reliable
//   • live preview frames (JPEG), sent one at a time (the next one goes when the iPad has shown the last)
//   • whole files (the finished video), with progress
// The web app checks window.standCaps.peer and falls back to its own internet route when it is missing.
//
// Setup: StandNativeExtras.shared.install(on: webView) right after the WKWebView is created, and
// NSBonjourServices = ["_stand-link._tcp", "_stand-link._udp"] in Info.plist (NSLocalNetworkUsageDescription
// is already there).

import Foundation
import UIKit
import WebKit
import MultipeerConnectivity
import CryptoKit
import Security

// Linking once (a code), then always: two devices only connect when they have been linked before
// with a four-digit code, or while both are on the "link a device" screen. Each linked device is
// remembered (its id and a secret key, made at the linking); every later connection proves, with
// that key, that it is the same device. Nothing from a device that has not proved it reaches the
// page, and nothing from the page goes to it.
private struct LinkedDevice: Codable { var key: String; var kind: String; var at: Double; var stale: Bool? }

// The link's secrets in the Keychain, for this device only: never in an iCloud or computer backup,
// never moved to a new iPad (a device restored from a backup is linked again with a code).
private enum StandKeychain {
    static func get(_ account: String) -> Data? { read(account).data }
    // (the status too: "not there" is not the same as "could not be read just now", which happens
    // before the iPhone is first unlocked after a restart; then nothing may be made anew or written over)
    static func read(_ account: String) -> (data: Data?, missing: Bool) {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: "stand.link",
                                kSecAttrAccount as String: account, kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var out: CFTypeRef?
        let st = SecItemCopyMatching(q as CFDictionary, &out)
        return (st == errSecSuccess ? out as? Data : nil, st == errSecItemNotFound)
    }
    @discardableResult static func set(_ account: String, _ data: Data) -> Bool {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: "stand.link", kSecAttrAccount as String: account]
        let attrs: [String: Any] = [kSecValueData as String: data, kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly]
        if SecItemUpdate(q as CFDictionary, attrs as CFDictionary) == errSecSuccess { return true }
        var add = q; for (k, v) in attrs { add[k] = v }
        return SecItemAdd(add as CFDictionary, nil) == errSecSuccess
    }
}

final class StandNativeExtras: NSObject {
    static let shared = StandNativeExtras()

    private weak var webView: WKWebView?
    private var inbox: [String] = []
    private var delivering = false
    private var framePending = false
    private let serviceType = "stand-link"          // must match NSBonjourServices
    private let token = UUID().uuidString           // decides which side invites (only one does)
    private var peerID: MCPeerID?
    private var session: MCSession?
    private var advertiser: MCNearbyServiceAdvertiser?
    private var browser: MCNearbyServiceBrowser?
    private var invited = [MCPeerID: Date]()
    private var displayName = "Stand"
    private var lastInvitation = Date.distantPast

    // linking (all of it touched on the main thread only)
    private let kind = UIDevice.current.userInterfaceIdiom == .phone ? "iPhone" : "iPad"
    private var keychainUnreadable = false
    private lazy var deviceId: String = {
        let r = StandKeychain.read("device")
        if let data = r.data, let s = String(data: data, encoding: .utf8), !s.isEmpty { return s }
        let s = UUID().uuidString
        if !r.missing { keychainUnreadable = true; return s }   // (for now only: the real one comes back once readable)
        StandKeychain.set("device", Data(s.utf8))
        UserDefaults.standard.removeObject(forKey: "standDeviceID")   // (an earlier test build kept it there)
        return s
    }()
    private lazy var linked: [String: LinkedDevice] = {
        // (an earlier test build kept them in the settings: moved to the Keychain, once)
        let d = UserDefaults.standard
        if let old = d.data(forKey: "standLinked") { d.removeObject(forKey: "standLinked"); StandKeychain.set("linked", old) }
        let r = StandKeychain.read("linked")
        if r.data == nil && !r.missing { keychainUnreadable = true }
        guard let data = r.data,
              let m = try? JSONDecoder().decode([String: LinkedDevice].self, from: data) else { return [:] }
        return m
    }()
    private func saveLinked() {
        if keychainUnreadable { StandLog.write("linked devices not saved: the Keychain could not be read"); return }   // (never written over with an empty list)
        if let data = try? JSONEncoder().encode(linked) { StandKeychain.set("linked", data) }
    }
    private var peerDev = [MCPeerID: String]()      // which device each peer is (from what it announces)
    private var peerKind = [MCPeerID: String]()
    private var verified = Set<MCPeerID>()          // proved to be a linked device: the only ones used
    private var myNonce = [MCPeerID: String]()
    private var pairMode = false
    private var pairTimer: Timer?
    private struct Pairing { let peer: MCPeerID; let shower: Bool; let code: String; var theirNonce: String; var tries: Int; var typed: String?; var pendingKey: String? }
    private var codesShown = 0                       // new codes in this time on the linking screen
    private var announced = Set<String>()           // devices not linked that were said to be nearby (once each)
    private var pairing: Pairing?
    private func allowed(_ d: String?) -> Bool { guard let d = d, !d.isEmpty, d != deviceId else { return false }; return pairMode || linked[d] != nil }

    // files being written from the page, then sent
    private var outFiles = [String: (url: URL, handle: FileHandle, meta: [String: Any])]()
    private var progressObservers = [String: NSKeyValueObservation]()

    func install(on webView: WKWebView) {
        self.webView = webView
        let ucc = webView.configuration.userContentController
        ucc.removeScriptMessageHandler(forName: "standPeer")
        ucc.add(WeakScriptHandler(self), name: "standPeer")
        let caps = "window.standCaps = Object.assign(window.standCaps || {}, { peer: 4 });"   // 3: file pieces are acknowledged; 4: linking with a code
        ucc.addUserScript(WKUserScript(source: caps, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        webView.evaluateJavaScript(caps, completionHandler: nil)
        // reminders for the practice plan (StandReminders.swift)
        StandReminders.shared.install(on: webView)
        // sound and microphone after the background, a call or an audio reset (StandAudioKeeper.swift)
        StandAudioKeeper.shared.install(on: webView)
        NotificationCenter.default.addObserver(self, selector: #selector(appActive), name: UIApplication.didBecomeActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(appBackground), name: UIApplication.didEnterBackgroundNotification, object: nil)
    }

    // MARK: - JavaScript helpers

    private func js(_ source: String) {
        DispatchQueue.main.async { [weak self] in self?.webView?.evaluateJavaScript(source, completionHandler: nil) }
    }
    private func jsValue(_ v: Any?) -> String {
        guard let v = v, let data = try? JSONSerialization.data(withJSONObject: v, options: [.fragmentsAllowed]),
              let out = String(data: data, encoding: .utf8) else { return "null" }
        return out
    }

    // MARK: - Messages from the page

    private func handle(_ op: String, _ body: [String: Any]) {
        switch op {
        case "start":
            startPeer(name: (body["name"] as? String) ?? UIDevice.current.name)
        case "stop":
            stopPeer()
        case "send":
            guard let str = body["data"] as? String, let data = ("J" + str).data(using: .utf8) else { return }
            send(data, mode: .reliable)
        case "frame":
            // a JPEG preview frame, base64
            guard let b64 = body["data"] as? String, let jpeg = Data(base64Encoded: b64) else { return }
            var data = Data([UInt8(ascii: "F")]); data.append(jpeg)
            send(data, mode: .reliable)
        case "fileBegin":
            guard let id = body["id"] as? String else { return }
            let ext = ((body["ext"] as? String) ?? "bin").filter { $0.isLetter || $0.isNumber }
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("out-" + id + "." + ext)
            FileManager.default.createFile(atPath: url.path, contents: nil)
            guard let h = try? FileHandle(forWritingTo: url) else { reportFile(id, error: "Could not prepare the file."); return }
            outFiles[id] = (url, h, (body["meta"] as? [String: Any]) ?? [:])
        case "fileChunk":
            guard let id = body["id"] as? String, let f = outFiles[id], let b64 = body["data"] as? String, let d = Data(base64Encoded: b64) else { return }
            do { try f.handle.write(contentsOf: d) } catch {
                // (a full disk: the sending stops with a message, never a crash)
                try? f.handle.close(); try? FileManager.default.removeItem(at: f.url); outFiles.removeValue(forKey: id)
                reportFile(id, error: "There is not enough space on this device.")
                return
            }
            // the page sends the next piece only when this one is written (a long video never piles up in memory)
            js("window.standPeerChunkOk && window.standPeerChunkOk(\(jsValue(id)))")
        case "fileEnd":
            guard let id = body["id"] as? String, let f = outFiles.removeValue(forKey: id) else { return }
            try? f.handle.close()
            sendFile(id: id, url: f.url, meta: f.meta)
        case "pairMode":
            setPairMode((body["on"] as? Bool) ?? false)
        case "pairCode":
            guard let code = body["code"] as? String, var p = pairing, !p.shower else { return }
            p.typed = code; pairing = p   // (kept: the other device must prove it knows the same code)
            sendAuth(["op": "pc", "m": mac(code, p.theirNonce + "|pair")], to: p.peer)
        case "pairList":
            reportLinked()
        case "pairForget":
            let d = body["d"] as? String
            let gone = d == nil ? Array(linked.keys) : [d!]
            for g in gone { linked.removeValue(forKey: g) }
            saveLinked()
            if let s = session { for p in s.connectedPeers where peerDev[p].map({ gone.contains($0) }) ?? false { verified.remove(p); s.cancelConnectPeer(p) } }
            reportLinked(); reportPeers()
        default:
            break
        }
    }

    // (only to the devices that proved they are linked)
    private var linkedPeers: [MCPeerID] { (session?.connectedPeers ?? []).filter { verified.contains($0) } }
    private func send(_ data: Data, mode: MCSessionSendDataMode) {
        guard let s = session else { return }
        let to = linkedPeers
        guard !to.isEmpty else { return }
        do { try s.send(data, toPeers: to, with: mode) } catch { }
    }

    private func sendFile(id: String, url: URL, meta: [String: Any]) {
        guard let s = session, let peer = linkedPeers.first else { reportFile(id, error: "The iPad is not connected."); return }
        var m = meta; m["id"] = id; m["ext"] = url.pathExtension
        let name = jsValue(m)
        let progress = s.sendResource(at: url, withName: name, toPeer: peer) { [weak self] error in
            DispatchQueue.main.async {
                self?.progressObservers.removeValue(forKey: id)
                try? FileManager.default.removeItem(at: url)
                if let e = error { self?.reportFile(id, error: e.localizedDescription) }
                else { self?.js("window.standPeerSent && window.standPeerSent(\(self?.jsValue(id) ?? "null"), null)") }
            }
        }
        if let p = progress {
            progressObservers[id] = p.observe(\.fractionCompleted, options: [.new]) { [weak self] p, _ in
                let f = p.fractionCompleted
                self?.js("window.standPeerProgress && window.standPeerProgress(\(self?.jsValue(id) ?? "null"), \(f), 'out')")
            }
        }
    }
    private func reportFile(_ id: String, error: String) {
        js("window.standPeerSent && window.standPeerSent(\(jsValue(id)), \(jsValue(error)))")
    }

    // MARK: - The link

    private func startPeer(name: String) {
        // (the device itself decides "iPhone" or "iPad": the two must never announce the same name)
        let kind = UIDevice.current.userInterfaceIdiom == .phone ? "iPhone" : "iPad"
        displayName = name.hasPrefix("Stand ") ? "Stand " + kind : String(name.prefix(50))
        if session != nil { reportPeers(); restartDiscovery(); return }
        let id = Self.savedPeerID(displayName)
        // (always encrypted, the same on both sides: "optional" made the two sometimes argue and drop)
        let s = MCSession(peer: id, securityIdentity: nil, encryptionPreference: .required)
        s.delegate = self
        peerID = id
        session = s
        let adv = MCNearbyServiceAdvertiser(peer: id, discoveryInfo: ["app": "stand", "t": token, "d": deviceId, "k": kind], serviceType: serviceType)
        adv.delegate = self
        advertiser = adv
        let br = MCNearbyServiceBrowser(peer: id, serviceType: serviceType)
        br.delegate = self
        browser = br
        adv.startAdvertisingPeer()
        br.startBrowsingForPeers()
        searching = true
        scheduleRest(after: 120)
    }

    // The same identity every time (Apple's advice): a new one each start left the other device
    // seeing an old "ghost" of this one, and the two then failed to connect, or dropped.
    private static func savedPeerID(_ name: String) -> MCPeerID {
        let d = UserDefaults.standard
        if let data = d.data(forKey: "standPeerID"), d.string(forKey: "standPeerName") == name,
           let id = try? NSKeyedUnarchiver.unarchivedObject(ofClass: MCPeerID.self, from: data) { return id }
        let id = MCPeerID(displayName: name)
        if let data = try? NSKeyedArchiver.archivedData(withRootObject: id, requiringSecureCoding: true) {
            d.set(data, forKey: "standPeerID"); d.set(name, forKey: "standPeerName")
        }
        return id
    }

    private func stopPeer() {
        restTimer?.invalidate(); restTimer = nil; searching = false
        advertiser?.stopAdvertisingPeer(); advertiser = nil
        browser?.stopBrowsingForPeers(); browser = nil
        session?.disconnect(); session = nil
        invited.removeAll(); seen.removeAll()
        verified.removeAll(); myNonce.removeAll(); pairing = nil
        reportPeers()
    }

    // MARK: - Linking

    private func mac(_ key: String, _ msg: String) -> String {
        let code = HMAC<SHA256>.authenticationCode(for: Data(msg.utf8), using: SymmetricKey(data: Data(key.utf8)))
        return Data(code).base64EncodedString()
    }
    private func sendAuth(_ obj: [String: Any], to peer: MCPeerID) {
        guard let s = session, s.connectedPeers.contains(peer),
              let json = try? JSONSerialization.data(withJSONObject: obj) else { return }
        var data = Data([UInt8(ascii: "A")]); data.append(json)
        do { try s.send(data, toPeers: [peer], with: .reliable) } catch { }
    }
    private func drop(_ peer: MCPeerID) {
        verified.remove(peer)
        if pairing?.peer == peer { pairing = nil }
        session?.cancelConnectPeer(peer)
    }
    private func setPairMode(_ on: Bool) {
        pairTimer?.invalidate(); pairTimer = nil
        pairMode = on
        if on { codesShown = 0 }
        if on {
            // (a few minutes at most: never left open by mistake)
            pairTimer = Timer.scheduledTimer(withTimeInterval: 300, repeats: false) { [weak self] _ in
                self?.setPairMode(false); self?.js("window.standPairEvent && window.standPairEvent('timeout', {})")
            }
            // the Stand devices already in sight are asked at once
            if let br = browser, session != nil {
                for (peer, info) in seen { invited.removeValue(forKey: peer); found(br, peer, info) }
            }
        } else if let p = pairing {
            pairing = nil
            if !verified.contains(p.peer) { session?.cancelConnectPeer(p.peer) }
        }
    }
    private func reportLinked() {
        let list = linked.map { ["d": $0.key, "kind": $0.value.kind, "at": $0.value.at, "stale": $0.value.stale ?? false] as [String: Any] }
            .sorted { (($0["at"] as? Double) ?? 0) > (($1["at"] as? Double) ?? 0) }
        js("window.standPairEvent && window.standPairEvent('list', \(jsValue(["list": list, "me": kind] as [String: Any])))")
    }
    // A device has just connected: each side says who it is, with a fresh random number to prove against.
    private func greet(_ peer: MCPeerID) {
        let n = UUID().uuidString
        myNonce[peer] = n
        let theirs = peerDev[peer]
        sendAuth(["op": "hi", "d": deviceId, "k": kind, "n": n, "pm": pairMode, "tr": theirs.map { linked[$0] != nil } ?? false], to: peer)
        // (not proved, and not linking, within a while: let go)
        DispatchQueue.main.asyncAfter(deadline: .now() + 25) { [weak self] in
            guard let self = self, let s = self.session, s.connectedPeers.contains(peer), !self.verified.contains(peer), self.pairing?.peer != peer else { return }
            StandLog.write("link: not proved, let go")
            self.drop(peer)
        }
    }
    private func handleAuth(_ peer: MCPeerID, _ m: [String: Any]) {
        guard let op = m["op"] as? String else { return }
        switch op {
        case "hi":
            guard let d = m["d"] as? String, let n = m["n"] as? String, d != deviceId else { drop(peer); return }
            if let known = peerDev[peer], known != d { drop(peer); return }   // (says it is another device than it announced)
            peerDev[peer] = d
            let theirKind = (m["k"] as? String) ?? "iPad"
            peerKind[peer] = theirKind
            let theyLink = (m["pm"] as? Bool) ?? false, theyTrust = (m["tr"] as? Bool) ?? false
            if pairMode && theyLink {
                // both on the linking screen: a new code, even if the two were linked before
                // (one at a time; a second "hi" from the same device makes no new code, but its newest
                // number is the one both prove against)
                guard pairing == nil else { if pairing?.peer == peer { pairing?.theirNonce = n } else { drop(peer) }; return }
                // (a few codes per visit to the linking screen: guessing by trying again and again is no use)
                codesShown += 1
                guard codesShown <= 4 else { drop(peer); js("window.standPairEvent && window.standPairEvent('timeout', {})"); return }
                let iShow = (kind == "iPad" && theirKind != "iPad") || (kind == theirKind && deviceId < d)
                let code = String(format: "%04d", Int.random(in: 0...9999))
                pairing = Pairing(peer: peer, shower: iShow, code: code, theirNonce: n, tries: 0, typed: nil, pendingKey: nil)
                if iShow { js("window.standPairEvent && window.standPairEvent('show', \(jsValue(["code": code, "kind": theirKind])))") }
                else { js("window.standPairEvent && window.standPairEvent('ask', \(jsValue(["kind": theirKind])))") }
            } else if let dev = linked[d], theyTrust {
                sendAuth(["op": "proof", "m": mac(dev.key, n + "|" + deviceId)], to: peer)
            } else if theyTrust {
                // linked there, but no longer here (forgotten on this device): they are told so
                sendAuth(["op": "forgot"], to: peer)
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in self?.drop(peer) }
            } else if !pairMode {
                drop(peer)
            }
        case "proof":
            guard let d = peerDev[peer], let dev = linked[d], let n = myNonce[peer], let got = m["m"] as? String else { drop(peer); return }
            if got == mac(dev.key, n + "|" + d) {
                verified.insert(peer)
                if linked[d]?.stale == true { linked[d]?.stale = nil; saveLinked(); reportLinked() }
                StandLog.write("link: linked device proved")
                reportPeers()
            } else {
                // (the two hold different keys: shown in Settings as "link again")
                StandLog.write("link: proof did not match")
                if linked[d]?.stale != true { linked[d]?.stale = true; saveLinked(); reportLinked() }
                drop(peer)
            }
        case "pc":
            // (the code typed on the other device, proved without sending it; at most five tries, then no more)
            guard var p = pairing, p.peer == peer, p.shower, p.pendingKey == nil, let n = myNonce[peer], let got = m["m"] as? String else { return }
            guard p.tries < 5 else { drop(peer); return }
            if got == mac(p.code, n + "|pair") {
                var bytes = [UInt8](repeating: 0, count: 32)
                _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
                let key = Data(bytes).base64EncodedString()
                p.pendingKey = key; pairing = p
                // the key goes, with this device's own proof that it knows the code; it is kept only
                // once the other device says it has it (a link dropped right then leaves no half link)
                sendAuth(["op": "key", "k": key, "m": mac(p.code, p.theirNonce + "|show")], to: peer)
            } else {
                p.tries += 1; pairing = p
                let left = 5 - p.tries
                sendAuth(["op": "bad", "left": left], to: peer)
                js("window.standPairEvent && window.standPairEvent('bad', \(jsValue(["left": left, "here": true] as [String: Any])))")
                if left <= 0 { drop(peer) }
            }
        case "key":
            // (kept only from the device that showed the code: it proves it knows it)
            guard let p = pairing, p.peer == peer, !p.shower, let typed = p.typed, let n = myNonce[peer], let d = peerDev[peer],
                  let key = m["k"] as? String, !key.isEmpty, let proof = m["m"] as? String else { return }
            guard proof == mac(typed, n + "|show") else { StandLog.write("link: key without proof"); drop(peer); return }
            let k = peerKind[peer] ?? "iPad"
            linked[d] = LinkedDevice(key: key, kind: k, at: Date().timeIntervalSince1970 * 1000, stale: nil)
            saveLinked()
            sendAuth(["op": "ok", "m": mac(key, p.theirNonce + "|ok")], to: peer)
            pairing = nil
            verified.insert(peer)
            StandLog.write("link: linked a new device")
            js("window.standPairEvent && window.standPairEvent('done', \(jsValue(["kind": k])))")
            reportLinked(); reportPeers()
        case "ok":
            // the other device has the key (it proves it): now it is kept here too
            guard let p = pairing, p.peer == peer, p.shower, let key = p.pendingKey, let n = myNonce[peer], let d = peerDev[peer],
                  let got = m["m"] as? String, got == mac(key, n + "|ok") else { return }
            let k = peerKind[peer] ?? "iPhone"
            linked[d] = LinkedDevice(key: key, kind: k, at: Date().timeIntervalSince1970 * 1000, stale: nil)
            saveLinked()
            pairing = nil
            verified.insert(peer)
            StandLog.write("link: linked a new device")
            js("window.standPairEvent && window.standPairEvent('done', \(jsValue(["kind": k])))")
            reportLinked(); reportPeers()
        case "bad":
            let left = (m["left"] as? Int) ?? 0
            js("window.standPairEvent && window.standPairEvent('bad', \(jsValue(["left": left])))")
        case "forgot":
            // (said by a device that has not proved anything: nothing is deleted on its word; the link
            // is shown as "link again" in Settings, and a new code puts it right)
            if let d = peerDev[peer], linked[d] != nil, linked[d]?.stale != true { linked[d]?.stale = true; saveLinked(); reportLinked() }
            drop(peer)
        default:
            break
        }
    }

    // After a drop the two find each other again WITHOUT stopping the looking: every stop and start of
    // the looking was followed, now and then, by iOS closing the app (a crash inside its own network
    // code a moment later; the logs showed it right after "looking again", each time). The looking
    // simply goes on; the devices it still sees are asked again, after a pause.
    private var seen: [MCPeerID: [String: String]] = [:]
    private var lastRestart = Date.distantPast
    private func restartDiscovery() {
        DispatchQueue.main.async {
            self.invited = self.invited.filter { Date().timeIntervalSince($0.value) < 10 }
            guard Date().timeIntervalSince(self.lastRestart) > 6 else { return }
            self.lastRestart = Date()
            guard !self.seen.isEmpty else { return }   // (none in sight: found again by itself when it comes)
            StandLog.write("link: asking again")
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                guard let br = self.browser, let s = self.session, s.connectedPeers.isEmpty, UIApplication.shared.applicationState == .active else { return }
                for (peer, info) in self.seen { self.invited.removeValue(forKey: peer); self.found(br, peer, info) }
            }
        }
    }
    // (the looking now goes on while Stand is open; it stops only when Stand goes to the background)
    private var searching = false
    private var restTimer: Timer?
    private func scheduleRest(after secs: TimeInterval) { }

    private func reportPeers() {
        if !Thread.isMainThread { DispatchQueue.main.async { self.reportPeers() }; return }
        let ps = linkedPeers
        let n = ps.count
        let names = ps.map { $0.displayName }
        js("window.standPeerState && window.standPeerState(\(n), \(jsValue(names)))")
    }

    @objc private func appBackground() {
        advertiser?.stopAdvertisingPeer()
        browser?.stopBrowsingForPeers()
        seen.removeAll()   // (found again when the looking starts again)
    }
    @objc private func appActive() {
        guard session != nil else { return }
        // (back from the background, where the looking was stopped: started again, after a pause)
        // (a moment only: back in Stand, the linked device is found again at once)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
            guard self.session != nil, UIApplication.shared.applicationState == .active else { return }
            self.advertiser?.startAdvertisingPeer(); self.browser?.startBrowsingForPeers(); self.searching = true
        }
    }
}

// MARK: - WKScriptMessageHandler

extension StandNativeExtras: WKScriptMessageHandler {
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any], let op = body["op"] as? String else { return }
        if message.name == "standPeer" { handle(op, body) }
    }
}

/// Keeps WKUserContentController from holding StandNativeExtras strongly.
private final class WeakScriptHandler: NSObject, WKScriptMessageHandler {
    weak var target: WKScriptMessageHandler?
    init(_ target: WKScriptMessageHandler) { self.target = target }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        target?.userContentController(userContentController, didReceive: message)
    }
}

// MARK: - MCSessionDelegate

extension StandNativeExtras: MCSessionDelegate {
    func session(_ session: MCSession, peer peerID: MCPeerID, didChange state: MCSessionState) {
        StandLog.write("link: \(peerID.displayName) " + (state == .connected ? "connected" : state == .connecting ? "connecting" : "not connected"))
        if state == .connected { DispatchQueue.main.async { guard self.session === session else { return }; self.greet(peerID) } }
        if state == .notConnected {
            DispatchQueue.main.async {
                self.invited.removeValue(forKey: peerID)
                self.verified.remove(peerID); self.myNonce.removeValue(forKey: peerID)
                if self.pairing?.peer == peerID { self.pairing = nil; self.js("window.standPairEvent && window.standPairEvent('lost', {})") }
                self.reportPeers()
            }
            // find each other again by itself
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
                guard let self = self, self.session === session, session.connectedPeers.isEmpty else { return }
                self.restartDiscovery()
            }
        }
    }
    func session(_ session: MCSession, didReceive data: Data, fromPeer peerID: MCPeerID) {
        guard let kind = data.first else { return }
        if kind == UInt8(ascii: "A") {
            guard let m = (try? JSONSerialization.jsonObject(with: data.dropFirst())) as? [String: Any] else { return }
            DispatchQueue.main.async { guard self.session === session else { return }; self.handleAuth(peerID, m) }
        } else if kind == UInt8(ascii: "J") {
            guard let str = String(data: data.dropFirst(), encoding: .utf8) else { return }
            DispatchQueue.main.async { guard self.verified.contains(peerID) else { return }; self.deliver(str) }
        } else if kind == UInt8(ascii: "F") {
            // (a picture still on its way to the page: this one is let go, never piled up)
            DispatchQueue.main.async {
                guard self.verified.contains(peerID), !self.framePending, let wv = self.webView else { return }
                self.framePending = true
                wv.callAsyncJavaScript("window.standPeerFrame && window.standPeerFrame(b)", arguments: ["b": data.dropFirst().base64EncodedString()], in: nil, in: .page) { [weak self] _ in self?.framePending = false }
            }
        }
    }
    // Messages to the page one after the other, each handed over as it is (a page of a score is a few
    // megabytes: written into a script, escaped, several at once, they took the memory of the iPad
    // or iPhone and the app was closed by iOS).
    private func deliver(_ str: String) {
        inbox.append(str)
        pumpInbox()
    }
    private func pumpInbox() {
        guard !delivering, !inbox.isEmpty, let wv = webView else { return }
        delivering = true
        let str = inbox.removeFirst()
        wv.callAsyncJavaScript("window.standPeerMessage && window.standPeerMessage(m)", arguments: ["m": str], in: nil, in: .page) { [weak self] _ in
            self?.delivering = false
            self?.pumpInbox()
        }
    }
    func session(_ session: MCSession, didReceive stream: InputStream, withName streamName: String, fromPeer peerID: MCPeerID) {}
    func session(_ session: MCSession, didStartReceivingResourceWithName resourceName: String, fromPeer peerID: MCPeerID, with progress: Progress) {
        let meta = (try? JSONSerialization.jsonObject(with: Data(resourceName.utf8))) as? [String: Any] ?? [:]
        let id = (meta["id"] as? String) ?? ""
        DispatchQueue.main.async {
            self.progressObservers["in-" + id] = progress.observe(\.fractionCompleted, options: [.new]) { [weak self] p, _ in
                self?.js("window.standPeerProgress && window.standPeerProgress(\(self?.jsValue(id) ?? "null"), \(p.fractionCompleted), 'in')")
            }
        }
    }
    func session(_ session: MCSession, didFinishReceivingResourceWithName resourceName: String, fromPeer peerID: MCPeerID, at localURL: URL?, withError error: Error?) {
        var meta = (try? JSONSerialization.jsonObject(with: Data(resourceName.utf8))) as? [String: Any] ?? [:]
        let id = (meta["id"] as? String) ?? UUID().uuidString
        DispatchQueue.main.async { self.progressObservers.removeValue(forKey: "in-" + id) }
        guard error == nil, let src = localURL else {
            js("window.standPeerFile && window.standPeerFile(\(jsValue(meta)), null, \(jsValue(error?.localizedDescription ?? "failed")))")
            return
        }
        let ext = ((meta["ext"] as? String) ?? "mp4").filter { $0.isLetter || $0.isNumber }
        let dest = incomingDir.appendingPathComponent("link-" + id + "." + (ext.isEmpty ? "mp4" : ext))
        try? FileManager.default.removeItem(at: dest)
        do { try FileManager.default.moveItem(at: src, to: dest) } catch {
            do { try FileManager.default.copyItem(at: src, to: dest) } catch {
                js("window.standPeerFile && window.standPeerFile(\(jsValue(meta)), null, \(jsValue(error.localizedDescription)))")
                return
            }
        }
        meta["size"] = (try? FileManager.default.attributesOfItem(atPath: dest.path)[.size] as? NSNumber)?.intValue ?? 0
        let done = meta
        DispatchQueue.main.async {
            // (from a device that has not proved it is linked: thrown away)
            guard self.verified.contains(peerID) else { try? FileManager.default.removeItem(at: dest); return }
            self.js("window.standPeerFile && window.standPeerFile(\(self.jsValue(done)), \(self.jsValue("/__incoming/" + dest.lastPathComponent)), null)")
        }
    }
}

// MARK: - Advertiser / browser

extension StandNativeExtras: MCNearbyServiceAdvertiserDelegate {
    func advertiser(_ advertiser: MCNearbyServiceAdvertiser, didReceiveInvitationFromPeer peerID: MCPeerID,
                    withContext context: Data?, invitationHandler: @escaping (Bool, MCSession?) -> Void) {
        // only Stand invites (the context says so, and which device it is); only a linked device, or
        // any Stand device while this one is on the linking screen
        let ctx = context.flatMap { String(data: $0, encoding: .utf8) } ?? ""
        let d: String? = ctx.hasPrefix("stand2|") ? String(ctx.dropFirst(7)) : nil
        // (the link's state is only ever touched on the main thread: an invitation arriving while the
        // link was being stopped read a session half taken down)
        DispatchQueue.main.async {
            let s = self.session
            // (already linked to that device: no second link to it, which made the two drop each other)
            let already = s?.connectedPeers.contains(peerID) ?? false
            let ok = self.allowed(d)
            if ok, let d = d { self.peerDev[peerID] = d }
            // (only an invitation taken holds back this device's own: one turned down, while this
            // device was not yet linking, must not stop it from asking a moment later)
            if ok && s != nil && !already { self.lastInvitation = Date() }
            invitationHandler(ok && s != nil && !already, s)
        }
    }
    func advertiser(_ advertiser: MCNearbyServiceAdvertiser, didNotStartAdvertisingPeer error: Error) {
        js("window.standPeerError && window.standPeerError(\(jsValue(error.localizedDescription)))")
    }
}

extension StandNativeExtras: MCNearbyServiceBrowserDelegate {
    func browser(_ browser: MCNearbyServiceBrowser, foundPeer peerID: MCPeerID, withDiscoveryInfo info: [String: String]?) {
        DispatchQueue.main.async { if info?["app"] == "stand" { self.seen[peerID] = info ?? [:] }; self.found(browser, peerID, info) }
    }
    private func found(_ browser: MCNearbyServiceBrowser, _ peerID: MCPeerID, _ info: [String: String]?) {
        guard info?["app"] == "stand", let s = session, browser === self.browser else { return }
        // a Stand device nearby that is not linked yet: the page is told, once (it may offer to link it);
        // nothing connects to it
        if let d = info?["d"], d != deviceId, linked[d] == nil, !pairMode, !announced.contains(d) {
            announced.insert(d)
            js("window.standPairEvent && window.standPairEvent('nearby', \(jsValue(["d": d, "kind": info?["k"] ?? "iPhone"])))")
        }
        // (only linked devices, or any while linking; an older Stand without linking is not asked)
        guard let d = info?["d"], allowed(d) else { return }
        peerDev[peerID] = d
        // only one of the two invites the other (the one with the smaller token); but when that one
        // cannot see this device (it happens: one side finds the other first), this one invites
        // after a few seconds instead
        guard let theirs = info?["t"] else { return }
        if token > theirs {
            // (2 s: long enough for the other one's own invitation to arrive first, short enough not to be felt)
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
                guard let self = self, let s2 = self.session, s2 === s, !s2.connectedPeers.contains(peerID) else { return }
                if Date().timeIntervalSince(self.lastInvitation) < 4 { return }
                if let at = self.invited[peerID], Date().timeIntervalSince(at) < 9 { return }
                self.invited[peerID] = Date()
                browser.invitePeer(peerID, to: s2, withContext: ("stand2|" + self.deviceId).data(using: .utf8), timeout: 8)
            }
            return
        }
        DispatchQueue.main.async {
            if let at = self.invited[peerID], Date().timeIntervalSince(at) < 9 { return }
            guard !s.connectedPeers.contains(peerID) else { return }
            self.invited[peerID] = Date()
            browser.invitePeer(peerID, to: s, withContext: ("stand2|" + self.deviceId).data(using: .utf8), timeout: 8)
        }
    }
    func browser(_ browser: MCNearbyServiceBrowser, lostPeer peerID: MCPeerID) {
        DispatchQueue.main.async { self.invited.removeValue(forKey: peerID); self.seen.removeValue(forKey: peerID) }
    }
    func browser(_ browser: MCNearbyServiceBrowser, didNotStartBrowsingForPeers error: Error) {
        js("window.standPeerError && window.standPeerError(\(jsValue(error.localizedDescription)))")
    }
}
