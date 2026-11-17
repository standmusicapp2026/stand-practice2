import Foundation
import MediaPlayer
import StoreKit

// Listen → Apple Music → a recording played here: the Music app's own player plays it (so a
// subscriber hears it whole, and it goes on behind Stand and with the screen locked), and Stand's
// bar at the bottom of the page works it: play, 5 seconds back and on, where it is, a passage
// repeated, close. Asked once: permission to use Apple Music. Not a subscriber, or no permission:
// said, and the Music app is offered instead.
final class StandMusicPlay {
    var event: (([String: Any]) -> Void)?
    private var timer: Timer?
    private var a: Double? = nil, b: Double? = nil
    private var said = ""
    private var title = ""
    private var storeID = ""
    private var ready = false
    private var player: MPMusicPlayerController { MPMusicPlayerController.systemMusicPlayer }

    func play(storeID: String, title: String) {
        self.title = title
        self.storeID = storeID
        a = nil; b = nil; ready = false; said = ""
        tell()
        let go = { [weak self] in
            guard let self else { return }
            self.player.setQueue(with: [storeID])
            self.player.prepareToPlay { err in
                DispatchQueue.main.async {
                    if let err {
                        self.event?(["op": "musicFailed", "why": "play", "detail": err.localizedDescription])
                        self.stopTimer()
                        return
                    }
                    self.ready = true
                    self.player.play()
                    self.startTimer()
                    self.tell()
                }
            }
        }
        // (permission to use Apple Music, asked the first time)
        let ask = { [weak self] in
            SKCloudServiceController.requestAuthorization { st in
                DispatchQueue.main.async {
                    guard st == .authorized else { self?.event?(["op": "musicFailed", "why": "permission"]); return }
                    go()
                }
            }
        }
        if SKCloudServiceController.authorizationStatus() == .authorized { go() } else { ask() }
    }

    func command(_ c: [String: Any]) {
        let p = player
        switch c["cmd"] as? String ?? "" {
        case "toggle", "play", "pause":
            let cmd = c["cmd"] as? String
            if cmd == "pause" || (cmd == "toggle" && p.playbackState == .playing) { p.pause() } else { p.play() }
        case "back": p.currentPlaybackTime = max(0, p.currentPlaybackTime - 5)
        case "fwd":
            let d = p.nowPlayingItem?.playbackDuration ?? 0
            p.currentPlaybackTime = d > 0 ? min(d - 0.5, p.currentPlaybackTime + 5) : p.currentPlaybackTime + 5
        case "loop":
            // one button: where it starts, where it ends (back to the start, and again), off
            let t = p.currentPlaybackTime
            if a != nil && b != nil { a = nil; b = nil }
            else if a == nil { a = t }
            else if let a0 = a, t > a0 + 0.3 { b = t; p.currentPlaybackTime = a0 }
            else { a = t }
        // (a moment kept: played from there)
        case "seek":
            let t = (c["value"] as? Double) ?? Double(c["value"] as? Int ?? 0)
            p.currentPlaybackTime = max(0, t); p.play()
        case "close":
            stop(); return
        default: break
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.08) { [weak self] in self?.tell() }
    }

    func stop() {
        player.stop()
        stopTimer()
        a = nil; b = nil; ready = false
        event?(["op": "closed", "kind": "music"])
    }

    private func startTimer() {
        stopTimer()
        timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
            guard let self else { return }
            // (a passage repeated: back to its start at its end)
            if let a0 = self.a, let b0 = self.b, self.player.currentPlaybackTime >= b0 { self.player.currentPlaybackTime = a0 }
            self.tell()
        }
    }
    private func stopTimer() { timer?.invalidate(); timer = nil }

    // how it is, for the bar (said again only when it changes)
    private func tell() {
        let p = player
        var m: [String: Any] = ["op": "status", "kind": "music", "ready": ready, "playing": p.playbackState == .playing,
                                "speed": 1, "t": Int(p.currentPlaybackTime.isFinite ? p.currentPlaybackTime : 0),
                                "d": Int(p.nowPlayingItem?.playbackDuration ?? 0), "title": title, "id": storeID]
        if let a { m["a"] = Int(a) } else { m["a"] = NSNull() }
        if let b { m["b"] = Int(b) } else { m["b"] = NSNull() }
        let k = "\(m["ready"]!)\(m["playing"]!)\(m["t"]!)\(m["d"]!)\(a ?? -1)\(b ?? -1)"
        if k == said { return }
        said = k
        event?(m)
    }
}
