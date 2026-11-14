import UIKit
import WebKit

// The little player that floats over the score: a YouTube or YouTube Music video, or a Spotify or
// Apple Music player, chosen from the recordings saved with a score (Listen). It is a web view of its
// own, loaded with an https address, so YouTube knows where its player is shown (a page of Stand's
// own address would be turned away). Drag it by its top bar; drag the corner of the bar to make it
// bigger or smaller; push it off the side of the screen to put it away (a small tab stays at the
// edge: tap it to bring the player back). Put away, a video pauses: YouTube does not let a video
// play where it cannot be seen. Nothing is drawn over the video itself.
final class StandMediaFloat: UIView, WKNavigationDelegate, WKUIDelegate {
    static let base = URL(string: "https://com.paulo.stand/")!
    private(set) var web: WKWebView!
    private let grab = UIView()
    private let pill = UIView()
    private let corner = UIImageView(image: UIImage(systemName: "arrow.up.left.and.arrow.down.right"))
    private let tab = UIButton(type: .system)
    private var loaded = false
    private var pending: [String: Any]?
    private(set) var kind = ""
    private var tuckedSide: CGFloat = 0     // -1 at the left edge, 1 at the right, 0 out
    private var shown = CGRect.zero         // the frame before it was put away
    var openOut: ((URL) -> Void)?
    var closed: (() -> Void)?
    var event: (([String: Any]) -> Void)?

    private final class Relay: NSObject, WKScriptMessageHandler {
        weak var owner: StandMediaFloat?
        func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) { owner?.fromPage(m.body as? [String: Any] ?? [:]) }
    }
    private let relay = Relay()

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = UIColor(red: 0.067, green: 0.082, blue: 0.114, alpha: 1)
        layer.cornerRadius = 14
        layer.cornerCurve = .continuous
        layer.shadowColor = UIColor.black.cgColor
        layer.shadowOpacity = 0.32
        layer.shadowRadius = 16
        layer.shadowOffset = CGSize(width: 0, height: 6)

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
        web.backgroundColor = .black
        web.scrollView.isScrollEnabled = false
        web.scrollView.bounces = false
        web.layer.cornerRadius = 12
        web.layer.maskedCorners = [.layerMinXMaxYCorner, .layerMaxXMaxYCorner]
        web.clipsToBounds = true
        #if DEBUG
        if #available(iOS 16.4, *) { web.isInspectable = true }
        #endif
        addSubview(web)

        grab.backgroundColor = .clear
        addSubview(grab)
        pill.backgroundColor = UIColor(white: 1, alpha: 0.45)
        pill.layer.cornerRadius = 2.5
        grab.addSubview(pill)
        corner.tintColor = UIColor(white: 1, alpha: 0.7)
        corner.contentMode = .center
        corner.isUserInteractionEnabled = true
        corner.accessibilityLabel = "Resize the player"
        grab.addSubview(corner)
        grab.accessibilityLabel = "Move the player"
        grab.isAccessibilityElement = true
        grab.addGestureRecognizer(UIPanGestureRecognizer(target: self, action: #selector(dragPlayer(_:))))
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
        let g: CGFloat = 26
        grab.frame = CGRect(x: 0, y: 0, width: bounds.width, height: g)
        pill.frame = CGRect(x: bounds.width / 2 - 18, y: 10, width: 36, height: 5)
        corner.frame = CGRect(x: bounds.width - 34, y: 0, width: 34, height: g)
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
    func command(_ c: [String: Any]) { js("window.mediaCmd && window.mediaCmd(\(json(c)))") }
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
        case "openOut":
            if let s = m["url"] as? String, let u = URL(string: s) { openOut?(u) }
        default: event?(m)
        }
    }

    // ---- sizes
    private var minW: CGFloat { kind == "youtube" ? 356 : 260 }
    private var minH: CGFloat { kind == "youtube" ? 26 + 200 + 44 : 26 + 80 + 44 }
    private func defaultFrame(in host: UIView) -> CGRect {
        let safe = host.safeAreaInsets
        let w = min(host.bounds.width - 32, kind == "youtube" ? 480 : 380)
        let h: CGFloat = kind == "youtube" ? 26 + w * 9 / 16 + 44 : kind == "spotify" ? 26 + 152 + 44 : 26 + 175 + 44
        return CGRect(x: host.bounds.width - w - 16 - safe.right, y: host.bounds.height - h - 16 - safe.bottom, width: w, height: h)
    }
    private func fitted(_ r: CGRect, in host: UIView) -> CGRect {
        let b = host.bounds.inset(by: host.safeAreaInsets)
        var f = r
        f.size.width = min(max(f.width, min(minW, b.width)), b.width)
        f.size.height = min(max(f.height, minH), b.height)
        f.origin.x = min(max(f.minX, b.minX), b.maxX - f.width)
        f.origin.y = min(max(f.minY, b.minY), b.maxY - f.height)
        return f
    }
    private func keep() { UserDefaults.standard.set(NSCoder.string(for: frame), forKey: "standMediaFrame.\(kind)") }

    // ---- moving, sizing, putting away
    private var start = CGRect.zero
    @objc private func dragPlayer(_ g: UIPanGestureRecognizer) {
        guard let host = superview, tuckedSide == 0 else { return }
        if g.state == .began { start = frame }
        let t = g.translation(in: host)
        frame.origin = CGPoint(x: start.minX + t.x, y: start.minY + t.y)
        if g.state == .ended || g.state == .cancelled {
            // (more than half of it off the side: put away at that edge)
            if frame.midX < host.bounds.minX + 10 { tuck(-1); return }
            if frame.midX > host.bounds.maxX - 10 { tuck(1); return }
            UIView.animate(withDuration: 0.2) { self.frame = self.fitted(self.frame, in: host) }
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
        let w = big ? minW : min(host.bounds.width * 0.7, 760)
        let h = kind == "youtube" ? 26 + w * 9 / 16 + 44 : frame.height
        UIView.animate(withDuration: 0.25) { self.frame = self.fitted(CGRect(x: self.frame.maxX - w, y: self.frame.maxY - h, width: w, height: h), in: host) }
        keep()
    }
    private func tuck(_ side: CGFloat) {
        guard let host = superview else { return }
        shown = fitted(CGRect(origin: CGPoint(x: side < 0 ? host.bounds.minX : host.bounds.maxX - frame.width, y: frame.minY), size: frame.size), in: host)
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
        UIView.animate(withDuration: 0.25) { self.frame = self.fitted(self.shown, in: host); self.layer.cornerRadius = 14 }
    }
    func hostResized() { guard let host = superview, tuckedSide == 0 else { return }; frame = fitted(frame, in: host) }

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
