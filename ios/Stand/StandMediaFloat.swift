import UIKit
import WebKit

// The little player that floats over the score: a YouTube or YouTube Music video, or a Spotify or
// Apple Music player, chosen from the recordings saved with a score (Listen). It is a web view of its
// own, loaded with an https address, so YouTube knows where its player is shown (a page of Stand's
// own address would be turned away).
//
// A video is the picture alone, with round corners: drag the picture to move it, pinch it with two
// fingers to make it bigger or smaller. Its buttons (play, −5, +5, speed, repeat, close) are not
// here: they stay in Stand's own bar at the bottom of the page, with the metronome and the drone
// (index.html, #mediaPill); nothing is ever drawn over the picture. It may be pushed half out of the screen at the left,
// the right or the bottom, so more of the music is free (the picture itself stays as big as YouTube
// asks; only the edge of the screen cuts it). Pushed further, it is put away: a small tab stays at the
// edge (tap it to bring the video back), and the video pauses: YouTube does not let a video play
// where it cannot be seen. The score is never made smaller for it.
//
// Spotify and Apple Music players keep a dark frame with a top bar to drag it by and a corner to
// size it, as their own players are touched everywhere.
final class StandMediaFloat: UIView, WKNavigationDelegate, WKUIDelegate, UIGestureRecognizerDelegate {
    static let base = URL(string: "https://com.paulo.stand/")!
    private(set) var web: WKWebView!
    private let grab = UIView()
    private let pill = UIView()
    private let corner = UIButton(type: .system)
    private let hideBtn = UIButton(type: .system)
    private let tab = UIButton(type: .system)
    private var loaded = false
    private var pending: [String: Any]?
    private(set) var kind = ""
    private var tuckedSide: CGFloat = 0     // -1 at the left edge, 1 at the right, 2 at the bottom, 0 out
    private var shown = CGRect.zero         // before it was put away: the frame (a video: its picture)
    private var keepRects: [CGRect] = []    // in the web view: what is touched for itself (not for dragging)
    var openOut: ((URL) -> Void)?
    var closed: (() -> Void)?
    var event: (([String: Any]) -> Void)?

    // (a frame with a bar: the sizes of the top bar, Stand's buttons under the picture, the margin)
    static let head: CGFloat = 26, bar: CGFloat = 40, pad: CGFloat = 6
    // (a video: Stand's buttons, and the space between them and the picture)
    static let barH: CGFloat = 44, gap: CGFloat = 8, radius: CGFloat = 14
    // (how much of it may be out of the screen, and how much further pushed puts it away)
    static let out: CGFloat = 0.5, away: CGFloat = 56

    // a video: the picture alone (the rest is the frame of the audio players)
    private var clean: Bool { kind == "youtube" }
    private var pic = CGRect.zero           // a video: where its picture is, in the host
    private var barShown = true             // its buttons showing (they go a few seconds after a touch)

    private final class Relay: NSObject, WKScriptMessageHandler {
        weak var owner: StandMediaFloat?
        func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) { owner?.fromPage(m.body as? [String: Any] ?? [:]) }
    }
    private let relay = Relay()
    private var darkDrag: UIPanGestureRecognizer!
    private var pinch: UIPinchGestureRecognizer!
    private var touchSeen: UILongPressGestureRecognizer!

    override init(frame: CGRect) {
        super.init(frame: frame)
        layer.shadowColor = UIColor.black.cgColor
        layer.shadowOpacity = 0.26
        layer.shadowRadius = 18
        layer.shadowOffset = CGSize(width: 0, height: 8)

        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        // (no picture in picture outside Stand: a video plays only where it can be seen)
        config.allowsPictureInPictureMediaPlayback = false
        config.websiteDataStore = .default()
        relay.owner = self
        config.userContentController.add(relay, name: "standMediaUI")
        web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.isOpaque = false
        web.backgroundColor = .clear
        web.scrollView.backgroundColor = .clear
        web.scrollView.isScrollEnabled = false
        web.scrollView.bounces = false
        web.scrollView.pinchGestureRecognizer?.isEnabled = false
        web.layer.cornerCurve = .continuous
        web.clipsToBounds = true
        // Stand away from the screen (home, another app, the iPad locked): a video pauses. Stand may
        // play sound in the background (the metronome), but YouTube does not let a video go on
        // playing where it is not seen.
        NotificationCenter.default.addObserver(self, selector: #selector(leaving), name: UIApplication.willResignActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(leaving), name: UIApplication.didEnterBackgroundNotification, object: nil)
        #if DEBUG
        if #available(iOS 16.4, *) { web.isInspectable = true }
        #endif
        addSubview(web)

        grab.backgroundColor = .clear
        addSubview(grab)
        pill.backgroundColor = UIColor(white: 1, alpha: 0.28)
        pill.layer.cornerRadius = 2
        grab.addSubview(pill)
        let small = UIImage.SymbolConfiguration(pointSize: 11, weight: .semibold)
        corner.setImage(UIImage(systemName: "arrow.up.left.and.arrow.down.right", withConfiguration: small), for: .normal)
        corner.tintColor = UIColor(white: 1, alpha: 0.45)
        corner.accessibilityLabel = "Resize the player"
        grab.addSubview(corner)
        hideBtn.setImage(UIImage(systemName: "minus", withConfiguration: small), for: .normal)
        hideBtn.tintColor = UIColor(white: 1, alpha: 0.45)
        hideBtn.accessibilityLabel = "Put the player away"
        hideBtn.addTarget(self, action: #selector(hideTapped), for: .touchUpInside)
        grab.addSubview(hideBtn)
        grab.accessibilityLabel = "Move the player"
        grab.isAccessibilityElement = false
        grab.addGestureRecognizer(UIPanGestureRecognizer(target: self, action: #selector(dragPlayer(_:))))
        // (a video: dragged by its picture; a frame: by its dark, round the player and between the buttons)
        darkDrag = UIPanGestureRecognizer(target: self, action: #selector(dragPlayer(_:)))
        darkDrag.delegate = self
        web.addGestureRecognizer(darkDrag)
        // (a video: two fingers make it bigger or smaller)
        pinch = UIPinchGestureRecognizer(target: self, action: #selector(pinchPlayer(_:)))
        pinch.delegate = self
        web.addGestureRecognizer(pinch)
        // (a video touched anywhere: its buttons come; the touch itself goes on to the video)
        touchSeen = UILongPressGestureRecognizer(target: self, action: #selector(touched(_:)))
        touchSeen.minimumPressDuration = 0
        touchSeen.cancelsTouchesInView = false
        touchSeen.delaysTouchesBegan = false
        touchSeen.delaysTouchesEnded = false
        touchSeen.delegate = self
        web.addGestureRecognizer(touchSeen)
        corner.addGestureRecognizer(UIPanGestureRecognizer(target: self, action: #selector(sizePlayer(_:))))
        let dbl = UITapGestureRecognizer(target: self, action: #selector(togglePlayerSize))
        dbl.numberOfTapsRequired = 2
        grab.addGestureRecognizer(dbl)

        tab.isHidden = true
        tab.setImage(UIImage(systemName: "play.rectangle.fill"), for: .normal)
        tab.tintColor = UIColor(white: 1, alpha: 0.9)
        tab.accessibilityLabel = "Bring the player back"
        tab.addTarget(self, action: #selector(untuck), for: .touchUpInside)
        addSubview(tab)
        restyle()

        if let path = Bundle.main.url(forResource: "media", withExtension: "html", subdirectory: "www"), let html = try? String(contentsOf: path, encoding: .utf8) {
            web.loadHTMLString(html, baseURL: StandMediaFloat.base)
        }
    }
    required init?(coder: NSCoder) { fatalError() }

    private static let dark = UIColor(red: 0.082, green: 0.094, blue: 0.122, alpha: 1)
    // (a video: nothing of its own round the picture; a frame: dark, with round corners)
    private func restyle() {
        let tucked = tuckedSide != 0
        backgroundColor = clean && !tucked ? .clear : (tucked ? StandMediaFloat.dark.withAlphaComponent(0.94) : StandMediaFloat.dark)
        layer.cornerCurve = .continuous
        if tucked {
            layer.cornerRadius = 12
            // (the tab comes out of the edge: round only where it is free)
            let left: CACornerMask = [.layerMaxXMinYCorner, .layerMaxXMaxYCorner]
            let right: CACornerMask = [.layerMinXMinYCorner, .layerMinXMaxYCorner]
            let bottom: CACornerMask = [.layerMinXMinYCorner, .layerMaxXMinYCorner]
            layer.maskedCorners = tuckedSide < 0 ? left : (tuckedSide == 1 ? right : bottom)
        } else {
            layer.cornerRadius = clean ? 0 : 16
            layer.maskedCorners = [.layerMinXMinYCorner, .layerMaxXMinYCorner, .layerMinXMaxYCorner, .layerMaxXMaxYCorner]
        }
        web.layer.cornerRadius = clean ? 0 : 12
        let all: CACornerMask = [.layerMinXMinYCorner, .layerMaxXMinYCorner, .layerMinXMaxYCorner, .layerMaxXMaxYCorner]
        let low: CACornerMask = [.layerMinXMaxYCorner, .layerMaxXMaxYCorner]
        web.layer.maskedCorners = clean ? all : low
        grab.isHidden = clean || tucked
        shade()
    }
    // (the shadow: under the picture and the buttons showing, not under the clear round them)
    private func shade() {
        if clean && tuckedSide == 0 {
            let p = UIBezierPath(roundedRect: picLocal, cornerRadius: StandMediaFloat.radius)
            layer.shadowPath = p.cgPath
            layer.shadowOpacity = 0.3
        } else {
            layer.shadowPath = nil
            layer.shadowOpacity = 0.26
        }
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        tab.frame = bounds
        if clean {
            web.frame = bounds
        } else {
            let g = StandMediaFloat.head
            grab.frame = CGRect(x: 0, y: 0, width: bounds.width, height: g)
            pill.frame = CGRect(x: bounds.width / 2 - 18, y: 11, width: 36, height: 4)
            corner.frame = CGRect(x: bounds.width - 40, y: 0, width: 40, height: g)
            hideBtn.frame = CGRect(x: 0, y: 0, width: 40, height: g)
            web.frame = CGRect(x: 0, y: g, width: bounds.width, height: max(0, bounds.height - g))
        }
        shade()
    }
    // A video: touches on the clear round the picture (and on the buttons while they are away) go
    // through to the score under it.
    override func point(inside p: CGPoint, with e: UIEvent?) -> Bool {
        guard clean, tuckedSide == 0 else { return super.point(inside: p, with: e) }
        return picLocal.contains(p)
    }

    // ---- from Stand's page
    func open(_ o: [String: Any], in host: UIView) {
        let was = clean
        kind = o["kind"] as? String ?? ""
        if superview == nil {
            host.addSubview(self)
            if clean {
                let saved = UserDefaults.standard.string(forKey: "standMediaPic.\(kind)").map { NSCoder.cgRect(for: $0) }
                setPic(fitPic(saved ?? defaultPic(in: host), in: host))
            } else {
                let saved = UserDefaults.standard.string(forKey: "standMediaFrame.\(kind)").map { NSCoder.cgRect(for: $0) }
                frame = fitted(saved ?? defaultFrame(in: host), in: host)
            }
        } else {
            if tuckedSide != 0 { untuck() }
            if clean && (!was || pic == .zero) { setPic(fitPic(defaultPic(in: host), in: host)) }
            if !clean && was { frame = fitted(defaultFrame(in: host), in: host) }
        }
        if clean { setPic(fitPic(pic, in: host)) } else { pic = .zero; frame = fitted(frame, in: host) }
        barShown = true
        restyle()
        setNeedsLayout()
        if loaded { run(o) } else { pending = o }
        // (where it is, for the self-test: on the screen, and as big as it must be)
        report("frame", host)
    }
    // (for the self-test: where it is; a video: where its picture is)
    private func report(_ op: String, _ host: UIView) {
        let r = clean ? pic : frame
        event?(["op": op, "x": r.minX, "y": r.minY, "w": r.width, "h": r.height, "hw": host.bounds.width, "hh": host.bounds.height, "clean": clean])
    }
    // (for the self-test: half out at the right edge with "r", at the bottom with "b", back on the
    // screen with "")
    func place(_ e: String) {
        guard let host = superview, tuckedSide == 0 else { return }
        if clean {
            var p = pic
            if e == "r" { p.origin.x = host.bounds.maxX - p.width * (1 - StandMediaFloat.out) }
            else if e == "b" { p.origin.y = host.bounds.maxY - p.height * (1 - StandMediaFloat.out) }
            else { p = defaultPic(in: host) }
            setPic(fitPic(p, in: host))
        } else {
            var f = frame
            f.origin.x = e == "r" ? host.bounds.maxX - f.width * (1 - StandMediaFloat.out) : host.bounds.maxX - f.width - 16 - host.safeAreaInsets.right
            frame = fitted(f, in: host)
        }
        keep()
        report("moved", host)
    }
    func command(_ c: [String: Any]) {
        // (put away at the edge and asked to play: it comes back, as a video plays only where it is seen)
        let cmd = c["cmd"] as? String ?? ""
        if tuckedSide != 0 && (cmd == "toggle" || cmd == "play") { untuck() }
        js("window.mediaCmd && window.mediaCmd(\(json(c)))")
    }
    // (the video's own page stopped while Stand was away: a frozen picture would stay over the score
    // with nothing to work it — it closes, and the score is free)
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { close() }
    @objc private func leaving() { if kind == "youtube", superview != nil { command(["cmd": "pause"]) } }
    func close() {
        js("window.mediaStop ? window.mediaStop() : (document.body.textContent = '')")
        removeFromSuperview()
        closed?()
    }

    private func run(_ o: [String: Any]) {
        var m = o
        m["clean"] = clean
        // (a video: its buttons are in Stand's bar at the bottom of the page)
        m["dock"] = clean
        if clean {
            let r = { (c: CGRect) -> [Int] in [Int(c.minX.rounded()), Int(c.minY.rounded()), Int(c.width.rounded()), Int(c.height.rounded())] }
            m["pic"] = r(picLocal); m["bar"] = r(barLocal)
            geoSaid = ""
        }
        js("window.mediaOpen(\(json(m)))")
    }
    private func js(_ s: String) { web.evaluateJavaScript(s, completionHandler: nil) }
    private func json(_ o: [String: Any]) -> String {
        guard let d = try? JSONSerialization.data(withJSONObject: o), let s = String(data: d, encoding: .utf8) else { return "{}" }
        return s
    }
    fileprivate func fromPage(_ m: [String: Any]) {
        switch m["op"] as? String ?? "" {
        case "loaded":
            loaded = true
            if let p = pending { pending = nil; run(p) }
        case "close": close()
        case "keep":
            keepRects = (m["rects"] as? [[Double]] ?? []).compactMap { $0.count == 4 ? CGRect(x: $0[0], y: $0[1], width: $0[2], height: $0[3]) : nil }
        case "bar":
            // (a video: its buttons came, or went)
            barShown = m["shown"] as? Bool ?? true
            shade()
        case "openOut":
            if let s = m["url"] as? String, let u = URL(string: s) { openOut?(u) }
        default: event?(m)
        }
    }

    // ---- a video: its picture, and its buttons under it (or above it), in the view
    private var picLocal = CGRect.zero
    private var barLocal = CGRect.zero
    private var geoSaid = ""
    // (a YouTube picture must have at least 200 × 200 points: 16:9, but never lower than 200)
    private func picHeight(_ w: CGFloat) -> CGFloat { max(200, (w * 9 / 16).rounded()) }
    private func defaultPic(in host: UIView) -> CGRect {
        let b = host.bounds.inset(by: host.safeAreaInsets)
        // (a video as small as it may be without black bands: 356 × 200; above Stand's bar of
        // buttons at the bottom of the page)
        let w = min(b.width - 32, 356), h = picHeight(w)
        return CGRect(x: b.maxX - w - 16, y: b.maxY - h - (b.width < 600 ? 150 : 116), width: w, height: h)
    }
    // (on the screen, but for as much as half of it beyond the left, the right or the bottom edge)
    private func fitPic(_ r: CGRect, in host: UIView) -> CGRect {
        let b = host.bounds.inset(by: host.safeAreaInsets), o = StandMediaFloat.out
        let maxW = max(200, min(b.width - 16, (b.height * 0.75 - 1) * 16 / 9))
        let w = min(max(r.width, 200), maxW), h = picHeight(w)
        var f = CGRect(x: r.minX, y: r.minY, width: w, height: h)
        f.origin.x = min(max(f.minX, host.bounds.minX - w * o), host.bounds.maxX - w * (1 - o))
        f.origin.y = min(max(f.minY, b.minY), host.bounds.maxY - h * (1 - o))
        return f
    }
    // (how far it is pushed beyond what may go out, and toward which edge)
    private func beyondPic(_ f: CGRect, in host: UIView) -> (CGFloat, CGFloat) {
        let o = StandMediaFloat.out
        let l = host.bounds.minX - f.width * o - f.minX
        let r = f.minX - (host.bounds.maxX - f.width * (1 - o))
        let d = f.minY - (host.bounds.maxY - f.height * (1 - o))
        if d > max(l, r, 0) { return (d, 2) }
        return l > r ? (max(l, 0), -1) : (max(r, 0), 1)
    }
    // The view is the picture alone (its buttons are in Stand's bar at the bottom of the page).
    private func setPic(_ p: CGRect) {
        guard superview != nil else { pic = p; return }
        pic = p
        frame = p
        picLocal = CGRect(origin: .zero, size: p.size)
        barLocal = .zero
        let geo = "{ pic: \(rectJS(picLocal)), bar: \(rectJS(barLocal)) }"
        if geo != geoSaid { geoSaid = geo; js("window.mediaLayout && window.mediaLayout(\(geo))") }
        shade()
    }
    private func rectJS(_ r: CGRect) -> String { "[\(Int(r.minX.rounded())), \(Int(r.minY.rounded())), \(Int(r.width.rounded())), \(Int(r.height.rounded()))]" }

    // ---- a frame: sizes
    // (Spotify and Apple Music)
    private var minW: CGFloat { 260 }
    private var minH: CGFloat { StandMediaFloat.head + 80 + StandMediaFloat.bar }
    private func naturalH(_ w: CGFloat) -> CGFloat {
        let h = StandMediaFloat.head, b = StandMediaFloat.bar
        return kind == "spotify" ? h + 152 + b : h + 175 + b
    }
    private func defaultFrame(in host: UIView) -> CGRect {
        let safe = host.safeAreaInsets
        let w = min(host.bounds.width - 32, 340)
        let h = naturalH(w)
        return CGRect(x: host.bounds.width - w - 16 - safe.right, y: host.bounds.height - h - 16 - safe.bottom, width: w, height: h)
    }
    // (on the screen, but for as much as half of it beyond the left or right edge)
    private func fitted(_ r: CGRect, in host: UIView) -> CGRect {
        let b = host.bounds.inset(by: host.safeAreaInsets), o = StandMediaFloat.out
        var f = r
        f.size.width = min(max(f.width, min(minW, b.width)), b.width)
        f.size.height = min(max(f.height, minH), b.height)
        f.origin.x = min(max(f.minX, host.bounds.minX - f.width * o), host.bounds.maxX - f.width * (1 - o))
        f.origin.y = min(max(f.minY, b.minY), b.maxY - f.height)
        return f
    }
    // (how far it is pushed beyond what may go out)
    private func beyond(_ f: CGRect, in host: UIView) -> CGFloat {
        let o = StandMediaFloat.out
        return max(host.bounds.minX - f.width * o - f.minX, f.minX - (host.bounds.maxX - f.width * (1 - o)), 0)
    }
    private func keep() {
        if clean { UserDefaults.standard.set(NSCoder.string(for: pic), forKey: "standMediaPic.\(kind)") }
        else { UserDefaults.standard.set(NSCoder.string(for: frame), forKey: "standMediaFrame.\(kind)") }
    }

    // ---- moving, sizing, putting away
    private var start = CGRect.zero
    private var pinching = false
    func gestureRecognizer(_ g: UIGestureRecognizer, shouldReceive t: UITouch) -> Bool {
        guard tuckedSide == 0 else { return false }
        if g === pinch || g === touchSeen { return clean }
        // (a touch in the web view moves it only where nothing there is touched for itself: a
        // video's own buttons along its bottom, Stand's buttons; a frame: the player, the buttons)
        guard g === darkDrag else { return true }
        // (a video: the whole picture drags it, but for a link in a message)
        if keepRects.isEmpty { return clean }
        let p = t.location(in: web)
        return !keepRects.contains { $0.insetBy(dx: -4, dy: -4).contains(p) }
    }
    // (beside the web view's own handling of touches: a tap on the video still plays or pauses it)
    func gestureRecognizer(_ g: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith o: UIGestureRecognizer) -> Bool { true }
    @objc private func touched(_ g: UILongPressGestureRecognizer) {
        if g.state == .began { js("window.mediaTouched && window.mediaTouched()") }
    }
    private var going = false
    @objc private func dragPlayer(_ g: UIPanGestureRecognizer) {
        guard let host = superview, tuckedSide == 0 else { return }
        if pinching { return }
        if g.state == .began { start = clean ? pic : frame }
        let t = g.translation(in: host)
        let raw = CGRect(origin: CGPoint(x: start.minX + t.x, y: start.minY + t.y), size: start.size)
        var over: CGFloat, side: CGFloat
        if clean { (over, side) = beyondPic(raw, in: host) } else { over = beyond(raw, in: host); side = raw.midX < host.bounds.midX ? -1 : 1 }
        if clean { setPic(fitPic(raw, in: host)) } else { frame = fitted(raw, in: host) }
        // (pushed on beyond half out: let go, it is put away; it shows that by fading)
        let away = over > StandMediaFloat.away
        if away != going { going = away; UIView.animate(withDuration: 0.15) { self.alpha = away ? 0.5 : 1 } }
        if g.state == .ended || g.state == .cancelled || g.state == .failed {
            if going { going = false; alpha = 1; shown = clean ? pic : frame; tuck(side, keepShown: true); return }
            keep()
        }
    }
    // (a video: two fingers make it bigger or smaller, about its middle)
    @objc private func pinchPlayer(_ g: UIPinchGestureRecognizer) {
        guard let host = superview, tuckedSide == 0, clean else { return }
        switch g.state {
        case .began:
            pinching = true; start = pic
            js("window.mediaHush && window.mediaHush()")
        case .changed:
            let w = max(200, start.width * g.scale), h = picHeight(w)
            setPic(fitPic(CGRect(x: start.midX - w / 2, y: start.midY - h / 2, width: w, height: h), in: host))
        default:
            pinching = false
            js("window.mediaTouched && window.mediaTouched()")
            // (a finger still down moves it on from where it is now)
            start = pic
            darkDrag.setTranslation(.zero, in: host)
            keep()
        }
    }
    @objc private func sizePlayer(_ g: UIPanGestureRecognizer) {
        guard let host = superview, tuckedSide == 0, !clean else { return }
        if g.state == .began { start = frame }
        let t = g.translation(in: host)
        // (the corner is at the top right: wider to the right, taller upwards)
        var f = CGRect(x: start.minX, y: start.minY + t.y, width: start.width + t.x, height: start.height - t.y)
        if f.width < minW { f.size.width = minW }
        if f.height < minH { f.origin.y = start.maxY - minH; f.size.height = minH }
        frame = fitted(f, in: host)
        if g.state == .ended || g.state == .cancelled { keep() }
    }
    @objc private func togglePlayerSize() {
        guard let host = superview, tuckedSide == 0, !clean else { return }
        let big = frame.width > min(host.bounds.width * 0.6, 620)
        let w = big ? minW : min(host.bounds.width * 0.7, 760)
        UIView.animate(withDuration: 0.25) { self.frame = self.fitted(CGRect(x: self.frame.maxX - w, y: self.frame.maxY - self.frame.height, width: w, height: self.frame.height), in: host) }
        keep()
    }
    @objc private func hideTapped() {
        guard let host = superview else { return }
        tuck(frame.midX < host.bounds.midX ? -1 : 1)
    }
    private func tuck(_ side: CGFloat, keepShown: Bool = false) {
        guard let host = superview else { return }
        if !keepShown { shown = clean ? pic : frame }
        tuckedSide = side
        // a video pauses when it cannot be seen; the other players stop
        if kind == "youtube" { command(["cmd": "pause"]) } else { js("document.querySelectorAll('iframe').forEach((f) => { f.dataset.src = f.src; f.src = 'about:blank'; })") }
        web.isHidden = true; tab.isHidden = false
        restyle()
        let b = host.bounds.inset(by: host.safeAreaInsets)
        let to: CGRect
        if side == 2 {
            to = CGRect(x: min(max(shown.midX - 42, b.minX + 8), b.maxX - 92), y: host.bounds.maxY - 30, width: 84, height: 30)
        } else {
            to = CGRect(x: side < 0 ? host.bounds.minX : host.bounds.maxX - 30, y: min(max(shown.midY - 42, b.minY), b.maxY - 84), width: 30, height: 84)
        }
        UIView.animate(withDuration: 0.25) { self.frame = to }
    }
    @objc private func untuck() {
        guard tuckedSide != 0, let host = superview else { return }
        tuckedSide = 0
        if kind != "youtube" { js("document.querySelectorAll('iframe').forEach((f) => { if (f.dataset.src) f.src = f.dataset.src; })") }
        tab.isHidden = true; web.isHidden = false
        barShown = true
        restyle()
        if clean { js("window.mediaTouched && window.mediaTouched()") }
        UIView.animate(withDuration: 0.25) {
            if self.clean { self.setPic(self.fitPic(self.shown, in: host)) } else { self.frame = self.fitted(self.shown, in: host) }
        }
        setNeedsLayout()
    }
    func hostResized() {
        guard let host = superview, tuckedSide == 0 else { return }
        if clean { setPic(fitPic(pic, in: host)) } else { frame = fitted(frame, in: host) }
    }

    // links inside a player (YouTube's own logo, Spotify's "open in Spotify") go out to their app
    func webView(_ webView: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if a.navigationType == .linkActivated, a.targetFrame?.isMainFrame ?? true, let u = a.request.url, u.scheme?.hasPrefix("http") == true { openOut?(u); decisionHandler(.cancel); return }
        decisionHandler(.allow)
    }
    func webView(_ webView: WKWebView, createWebViewWith c: WKWebViewConfiguration, for a: WKNavigationAction, windowFeatures f: WKWindowFeatures) -> WKWebView? {
        if let u = a.request.url { openOut?(u) }
        return nil
    }
}
