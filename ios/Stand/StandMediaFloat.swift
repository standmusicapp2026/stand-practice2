import UIKit
import WebKit

// The little player that floats over the score: a YouTube or YouTube Music video, or a Spotify or
// Apple Music player, chosen from the recordings saved with a score (Listen). It is a web view of its
// own, loaded with an https address, so YouTube knows where its player is shown (a page of Stand's
// own address would be turned away). Drag it by any of its dark edge (the top bar, the margin round
// the picture, the bar of buttons between the buttons); drag the corner to make it bigger or smaller.
// It may be pushed half out of the screen at the left or right, so more of the music is free (the
// player itself stays as big as YouTube asks; only the edge of the screen cuts it). Pushed further,
// it is put away, as with the − button: a small tab stays at the edge (tap it to bring the player
// back), and a video pauses: YouTube does not let a video play where it cannot be seen. Nothing is
// drawn over the video, and the score is never made smaller for it.
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
    private var tuckedSide: CGFloat = 0     // -1 at the left edge, 1 at the right, 0 out
    private var shown = CGRect.zero         // the frame before it was put away
    private var keepRects: [CGRect] = []    // in the web view: the picture and the buttons (not for dragging)
    var openOut: ((URL) -> Void)?
    var closed: (() -> Void)?
    var event: (([String: Any]) -> Void)?

    // (the sizes: the top bar, Stand's buttons under the picture, and the margin round the picture)
    static let head: CGFloat = 26, bar: CGFloat = 40, pad: CGFloat = 6
    // (how much of it may be out of the screen, and how much further pushed puts it away)
    static let out: CGFloat = 0.5, away: CGFloat = 56

    private final class Relay: NSObject, WKScriptMessageHandler {
        weak var owner: StandMediaFloat?
        func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) { owner?.fromPage(m.body as? [String: Any] ?? [:]) }
    }
    private let relay = Relay()

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = UIColor(red: 0.082, green: 0.094, blue: 0.122, alpha: 1)
        layer.cornerRadius = 16
        layer.cornerCurve = .continuous
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
        web.layer.cornerRadius = 12
        web.layer.cornerCurve = .continuous
        web.layer.maskedCorners = [.layerMinXMaxYCorner, .layerMaxXMaxYCorner]
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
        // (the dark round the picture and between the buttons moves it too)
        let darkDrag = UIPanGestureRecognizer(target: self, action: #selector(dragPlayer(_:)))
        darkDrag.delegate = self
        web.addGestureRecognizer(darkDrag)
        corner.addGestureRecognizer(UIPanGestureRecognizer(target: self, action: #selector(sizePlayer(_:))))
        let dbl = UITapGestureRecognizer(target: self, action: #selector(togglePlayerSize))
        dbl.numberOfTapsRequired = 2
        grab.addGestureRecognizer(dbl)

        tab.isHidden = true
        tab.setImage(UIImage(systemName: "play.rectangle.fill"), for: .normal)
        tab.tintColor = .white
        tab.accessibilityLabel = "Bring the player back"
        tab.addTarget(self, action: #selector(untuck), for: .touchUpInside)
        addSubview(tab)

        if let path = Bundle.main.url(forResource: "media", withExtension: "html", subdirectory: "www"), let html = try? String(contentsOf: path, encoding: .utf8) {
            web.loadHTMLString(html, baseURL: StandMediaFloat.base)
        }
    }
    required init?(coder: NSCoder) { fatalError() }

    override func layoutSubviews() {
        super.layoutSubviews()
        let g = StandMediaFloat.head
        grab.frame = CGRect(x: 0, y: 0, width: bounds.width, height: g)
        pill.frame = CGRect(x: bounds.width / 2 - 18, y: 11, width: 36, height: 4)
        corner.frame = CGRect(x: bounds.width - 40, y: 0, width: 40, height: g)
        hideBtn.frame = CGRect(x: 0, y: 0, width: 40, height: g)
        web.frame = CGRect(x: 0, y: g, width: bounds.width, height: max(0, bounds.height - g))
        tab.frame = bounds
    }

    // ---- from Stand's page
    func open(_ o: [String: Any], in host: UIView) {
        kind = o["kind"] as? String ?? ""
        if superview == nil {
            host.addSubview(self)
            let saved = UserDefaults.standard.string(forKey: "standMediaFrame.\(kind)").map { NSCoder.cgRect(for: $0) }
            frame = fitted(saved ?? defaultFrame(in: host), in: host)
        } else if tuckedSide != 0 { untuck() }
        // (a video needs room for its picture; an audio player less)
        frame = fitted(frame, in: host)
        if loaded { run(o) } else { pending = o }
        // (where it is, for the self-test: on the screen, and as big as it must be)
        event?(["op": "frame", "x": frame.minX, "y": frame.minY, "w": frame.width, "h": frame.height, "hw": host.bounds.width, "hh": host.bounds.height])
    }
    // (for the self-test: half out at the right edge with "r", back on the screen with "")
    func place(_ e: String) {
        guard let host = superview, tuckedSide == 0 else { return }
        var f = frame
        f.origin.x = e == "r" ? host.bounds.maxX - f.width * (1 - StandMediaFloat.out) : host.bounds.maxX - f.width - 16 - host.safeAreaInsets.right
        frame = fitted(f, in: host)
        keep()
        event?(["op": "moved", "x": frame.minX, "y": frame.minY, "w": frame.width, "h": frame.height, "hw": host.bounds.width, "hh": host.bounds.height])
    }
    func command(_ c: [String: Any]) { js("window.mediaCmd && window.mediaCmd(\(json(c)))") }
    @objc private func leaving() { if kind == "youtube", superview != nil { command(["cmd": "pause"]) } }
    func close() {
        js("document.body.textContent = ''")
        removeFromSuperview()
        closed?()
    }

    private func run(_ o: [String: Any]) { js("window.mediaOpen(\(json(o)))") }
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
        case "openOut":
            if let s = m["url"] as? String, let u = URL(string: s) { openOut?(u) }
        default: event?(m)
        }
    }

    // ---- sizes
    // (a YouTube picture must have at least 200 × 200 points; narrower than 16:9 it is letterboxed)
    private var minW: CGFloat { kind == "youtube" ? 200 + 2 * StandMediaFloat.pad : 260 }
    private var minH: CGFloat { StandMediaFloat.head + (kind == "youtube" ? 200 : 80) + StandMediaFloat.bar }
    private func naturalH(_ w: CGFloat) -> CGFloat {
        let p = StandMediaFloat.pad, h = StandMediaFloat.head, b = StandMediaFloat.bar
        return kind == "youtube" ? max(minH, h + (w - 2 * p) * 9 / 16 + b) : kind == "spotify" ? h + 152 + b : h + 175 + b
    }
    private func defaultFrame(in host: UIView) -> CGRect {
        let safe = host.safeAreaInsets
        // (a video as small as it may be without black bands: 356 × 200)
        let w = min(host.bounds.width - 32, kind == "youtube" ? 356 + 2 * StandMediaFloat.pad : 340)
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
    private func keep() { UserDefaults.standard.set(NSCoder.string(for: frame), forKey: "standMediaFrame.\(kind)") }

    // ---- moving, sizing, putting away
    private var start = CGRect.zero
    // (a touch in the web view moves it only on the dark: not on the picture, not on a button)
    func gestureRecognizer(_ g: UIGestureRecognizer, shouldReceive t: UITouch) -> Bool {
        guard tuckedSide == 0, !keepRects.isEmpty else { return false }
        let p = t.location(in: web)
        return !keepRects.contains { $0.insetBy(dx: -4, dy: -4).contains(p) }
    }
    // (beside the web view's own handling of touches, which does nothing with them there)
    func gestureRecognizer(_ g: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith o: UIGestureRecognizer) -> Bool { true }
    private var going = false
    @objc private func dragPlayer(_ g: UIPanGestureRecognizer) {
        guard let host = superview, tuckedSide == 0 else { return }
        if g.state == .began { start = frame }
        let t = g.translation(in: host)
        let raw = CGRect(origin: CGPoint(x: start.minX + t.x, y: start.minY + t.y), size: start.size)
        frame = fitted(raw, in: host)
        // (pushed on beyond half out: let go, it is put away; it shows that by fading)
        let away = beyond(raw, in: host) > StandMediaFloat.away
        if away != going { going = away; UIView.animate(withDuration: 0.15) { self.alpha = away ? 0.5 : 1 } }
        if g.state == .ended || g.state == .cancelled || g.state == .failed {
            if going { going = false; alpha = 1; shown = frame; tuck(raw.midX < host.bounds.midX ? -1 : 1, keepShown: true); return }
            keep()
        }
    }
    @objc private func sizePlayer(_ g: UIPanGestureRecognizer) {
        guard let host = superview, tuckedSide == 0 else { return }
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
        guard let host = superview, tuckedSide == 0 else { return }
        let big = frame.width > min(host.bounds.width * 0.6, 620)
        let w = big ? (kind == "youtube" ? 356 + 2 * StandMediaFloat.pad : minW) : min(host.bounds.width * 0.7, 760)
        let h = kind == "youtube" ? naturalH(w) : frame.height
        UIView.animate(withDuration: 0.25) { self.frame = self.fitted(CGRect(x: self.frame.maxX - w, y: self.frame.maxY - h, width: w, height: h), in: host) }
        keep()
    }
    @objc private func hideTapped() {
        guard let host = superview else { return }
        tuck(frame.midX < host.bounds.midX ? -1 : 1)
    }
    private func tuck(_ side: CGFloat, keepShown: Bool = false) {
        guard let host = superview else { return }
        if !keepShown { shown = frame }
        tuckedSide = side
        // a video pauses when it cannot be seen; the other players stop
        if kind == "youtube" { command(["cmd": "pause"]) } else { js("document.querySelectorAll('iframe').forEach((f) => { f.dataset.src = f.src; f.src = 'about:blank'; })") }
        web.isHidden = true; grab.isHidden = true; tab.isHidden = false
        let b = host.bounds.inset(by: host.safeAreaInsets)
        UIView.animate(withDuration: 0.25) {
            self.frame = CGRect(x: side < 0 ? host.bounds.minX : host.bounds.maxX - 34, y: min(max(self.shown.midY - 45, b.minY), b.maxY - 90), width: 34, height: 90)
            self.layer.cornerRadius = 10
        }
    }
    @objc private func untuck() {
        guard tuckedSide != 0, let host = superview else { return }
        tuckedSide = 0
        if kind != "youtube" { js("document.querySelectorAll('iframe').forEach((f) => { if (f.dataset.src) f.src = f.dataset.src; })") }
        tab.isHidden = true; web.isHidden = false; grab.isHidden = false
        UIView.animate(withDuration: 0.25) { self.frame = self.fitted(self.shown, in: host); self.layer.cornerRadius = 16 }
    }
    func hostResized() {
        guard let host = superview, tuckedSide == 0 else { return }
        frame = fitted(frame, in: host)
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
