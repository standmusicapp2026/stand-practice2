import UIKit
import WebKit

// The little player that floats over the score: a YouTube or YouTube Music video, or a Spotify or
// Apple Music player, chosen from the recordings saved with a score (Listen). It is a web view of its
// own, loaded with an https address, so YouTube knows where its player is shown (a page of Stand's
// own address would be turned away). Drag it by its top bar; drag the corner to make it bigger or
// smaller. Pushed against the left, right or bottom edge of the screen it settles there beside the
// music: the score makes room for it (nothing of the music is under it), and it goes on playing.
// Dragged away from the edge, it floats again and the score takes the whole screen. The − button
// puts it away (a small tab stays at the edge: tap it to bring the player back); put away, a video
// pauses: YouTube does not let a video play where it cannot be seen. Nothing is drawn over the video.
final class StandMediaFloat: UIView, WKNavigationDelegate, WKUIDelegate {
    static let base = URL(string: "https://com.paulo.stand/")!
    private(set) var web: WKWebView!
    private let grab = UIView()
    private let pill = UIView()
    private let corner = UIButton(type: .system)
    private let hideBtn = UIButton(type: .system)
    private let tab = UIButton(type: .system)
    private let zone = UIView()             // where it will settle, shown while it is dragged to an edge
    private var loaded = false
    private var pending: [String: Any]?
    private(set) var kind = ""
    private var tuckedSide: CGFloat = 0     // -1 at the left edge, 1 at the right, 0 out
    private var shown = CGRect.zero         // the frame before it was put away
    private var shownEdge = ""              // and the edge it was beside then
    var openOut: ((URL) -> Void)?
    var closed: (() -> Void)?
    var event: (([String: Any]) -> Void)?

    // (the sizes: the top bar, Stand's buttons under the picture, and the margin round the picture)
    static let head: CGFloat = 24, bar: CGFloat = 40, pad: CGFloat = 6

    private final class Relay: NSObject, WKScriptMessageHandler {
        weak var owner: StandMediaFloat?
        func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) { owner?.fromPage(m.body as? [String: Any] ?? [:]) }
    }
    private let relay = Relay()

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = UIColor(red: 0.075, green: 0.086, blue: 0.114, alpha: 1)
        layer.cornerRadius = 16
        layer.cornerCurve = .continuous
        layer.borderWidth = 1
        layer.borderColor = UIColor(white: 1, alpha: 0.09).cgColor
        layer.shadowColor = UIColor.black.cgColor
        layer.shadowOpacity = 0.28
        layer.shadowRadius = 22
        layer.shadowOffset = CGSize(width: 0, height: 10)

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
        pill.backgroundColor = UIColor(white: 1, alpha: 0.32)
        pill.layer.cornerRadius = 2
        grab.addSubview(pill)
        let small = UIImage.SymbolConfiguration(pointSize: 12, weight: .semibold)
        corner.setImage(UIImage(systemName: "arrow.up.left.and.arrow.down.right", withConfiguration: small), for: .normal)
        corner.tintColor = UIColor(white: 1, alpha: 0.6)
        corner.accessibilityLabel = "Resize the player"
        grab.addSubview(corner)
        hideBtn.setImage(UIImage(systemName: "minus", withConfiguration: small), for: .normal)
        hideBtn.tintColor = UIColor(white: 1, alpha: 0.6)
        hideBtn.accessibilityLabel = "Put the player away"
        hideBtn.addTarget(self, action: #selector(hideTapped), for: .touchUpInside)
        grab.addSubview(hideBtn)
        grab.accessibilityLabel = "Move the player"
        grab.isAccessibilityElement = false
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

        zone.isUserInteractionEnabled = false
        zone.backgroundColor = UIColor(red: 0.5, green: 0.65, blue: 1, alpha: 0.14)
        zone.layer.borderColor = UIColor(red: 0.5, green: 0.65, blue: 1, alpha: 0.7).cgColor
        zone.layer.borderWidth = 2
        zone.layer.cornerRadius = 16
        zone.layer.cornerCurve = .continuous

        if let path = Bundle.main.url(forResource: "media", withExtension: "html", subdirectory: "www"), let html = try? String(contentsOf: path, encoding: .utf8) {
            web.loadHTMLString(html, baseURL: StandMediaFloat.base)
        }
    }
    required init?(coder: NSCoder) { fatalError() }

    override func layoutSubviews() {
        super.layoutSubviews()
        let g = StandMediaFloat.head
        grab.frame = CGRect(x: 0, y: 0, width: bounds.width, height: g)
        pill.frame = CGRect(x: bounds.width / 2 - 16, y: 9, width: 32, height: 4)
        corner.frame = CGRect(x: bounds.width - 36, y: 0, width: 36, height: g)
        hideBtn.frame = CGRect(x: 0, y: 0, width: 36, height: g)
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
            // (beside the music again if it was there the last time)
            edge = ""
            let e = UserDefaults.standard.string(forKey: "standMediaEdge") ?? ""
            if !e.isEmpty { settle(e, animated: false) }
        } else if tuckedSide != 0 { untuck() }
        // (a video needs room for its picture; an audio player less)
        frame = fitted(frame, in: host)
        if !edge.isEmpty { settle(edge, animated: false) }
        if loaded { run(o) } else { pending = o }
        // (where it is, for the self-test: on the screen, and as big as it must be)
        event?(["op": "frame", "x": frame.minX, "y": frame.minY, "w": frame.width, "h": frame.height, "hw": host.bounds.width, "hh": host.bounds.height])
    }
    // (beside the music at that edge, or floating again with "": as when dragged there)
    func place(_ e: String) {
        guard superview != nil, tuckedSide == 0 else { return }
        if e.isEmpty { setEdge(""); if let host = superview { frame = fitted(frame.offsetBy(dx: -60, dy: -60), in: host) } } else { settle(e) }
        keep()
    }
    func command(_ c: [String: Any]) { js("window.mediaCmd && window.mediaCmd(\(json(c)))") }
    @objc private func leaving() { if kind == "youtube", superview != nil { command(["cmd": "pause"]) } }
    func close() {
        js("document.body.textContent = ''")
        zone.removeFromSuperview()
        setEdge("")
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

    // ---- beside the music: at the left, right or bottom edge, the score makes room
    private var edge = ""                   // "l", "r", "b", or "" floating
    private var narrow: Bool { (superview?.bounds.width ?? 1000) < 600 }
    // (the edge it is pushed against, while dragged: past the edge of the screen by a little)
    private func edgeFor(_ f: CGRect) -> String {
        guard let host = superview else { return "" }
        let b = host.bounds.inset(by: host.safeAreaInsets)
        // (on a phone there is no room beside the music: it goes only under it, pushed down)
        let over: [(String, CGFloat)] = [("l", narrow ? 0 : b.minX - f.minX), ("r", narrow ? 0 : f.maxX - b.maxX), ("b", f.maxY - b.maxY)]
        guard let best = over.max(by: { $0.1 < $1.1 }), best.1 > 14 else { return "" }
        return best.0
    }
    private func frameAt(_ e: String) -> CGRect {
        guard let host = superview else { return frame }
        let b = host.bounds.inset(by: host.safeAreaInsets), m: CGFloat = 8
        var f = frame
        switch e {
        case "l", "r":
            f.size.width = min(max(f.width, minW), max(minW, b.width * 0.42))
            f.size.height = max(naturalH(f.width), minH)
            f.origin.x = e == "l" ? b.minX + m : b.maxX - f.width - m
        case "b":
            f.size.height = min(max(f.height, minH), max(minH, b.height * 0.45))
            f.origin.y = b.maxY - f.height - m
        default: break
        }
        return fitted(f, in: host)
    }
    private func settle(_ e0: String, animated: Bool = true) {
        let e = narrow && !e0.isEmpty ? "b" : e0
        let f = frameAt(e)
        if animated { UIView.animate(withDuration: 0.25, delay: 0, options: .curveEaseOut) { self.frame = f } } else { frame = f }
        setEdge(e, f)
    }
    // (tells the page how much room to leave the player, from that edge of the screen)
    private func setEdge(_ e: String, _ f: CGRect? = nil) {
        edge = e
        UserDefaults.standard.set(e, forKey: "standMediaEdge")
        guard let host = superview else { event?(["op": "side", "edge": "", "inset": 0]); return }
        let r = f ?? frame, m: CGFloat = 8
        let inset: CGFloat = e == "l" ? r.maxX + m - host.bounds.minX : e == "r" ? host.bounds.maxX - r.minX + m : e == "b" ? host.bounds.maxY - r.minY + m : 0
        event?(["op": "side", "edge": e, "inset": max(0, inset.rounded())])
    }
    private func showZone(_ e: String) {
        guard let host = superview else { return }
        if e.isEmpty { if zone.superview != nil { UIView.animate(withDuration: 0.15, animations: { self.zone.alpha = 0 }) { _ in if self.zone.alpha == 0 { self.zone.removeFromSuperview() } } }; return }
        let f = frameAt(e).insetBy(dx: -4, dy: -4)
        if zone.superview == nil { zone.alpha = 0; zone.frame = f; host.insertSubview(zone, belowSubview: self) }
        UIView.animate(withDuration: 0.15) { self.zone.alpha = 1; self.zone.frame = f }
    }

    // ---- moving, sizing, putting away
    private var start = CGRect.zero
    @objc private func dragPlayer(_ g: UIPanGestureRecognizer) {
        guard let host = superview, tuckedSide == 0 else { return }
        if g.state == .began { start = frame }
        let t = g.translation(in: host)
        frame.origin = CGPoint(x: start.minX + t.x, y: start.minY + t.y)
        // (pushed against an edge: it shows where it will go; let go there, it settles beside the music)
        let e = edgeFor(frame)
        // (already beside the music and only moved along that edge: it stays there)
        let along = !edge.isEmpty && e.isEmpty && frameAt(edge).intersects(frame) && abs((edge == "b" ? frame.midY - frameAt(edge).midY : frame.midX - frameAt(edge).midX)) < 40
        showZone(e.isEmpty && along ? edge : e)
        if g.state == .ended || g.state == .cancelled {
            showZone("")
            if !e.isEmpty || along { settle(e.isEmpty ? edge : e) }
            else {
                if !edge.isEmpty { setEdge("") }
                UIView.animate(withDuration: 0.2) { self.frame = self.fitted(self.frame, in: host) }
            }
            keep()
        }
    }
    @objc private func sizePlayer(_ g: UIPanGestureRecognizer) {
        guard let host = superview, tuckedSide == 0 else { return }
        if g.state == .began { start = frame }
        let t = g.translation(in: host)
        // (the corner is at the top right: wider to the right, taller upwards; at the right edge,
        // wider to the left)
        let dx = edge == "r" ? -t.x : t.x
        var f = CGRect(x: edge == "r" ? start.maxX - (start.width + dx) : start.minX, y: start.minY + t.y, width: start.width + dx, height: start.height - t.y)
        if f.width < minW { if edge == "r" { f.origin.x = start.maxX - minW }; f.size.width = minW }
        if f.height < minH { f.origin.y = start.maxY - minH; f.size.height = minH }
        frame = fitted(f, in: host)
        if g.state == .ended || g.state == .cancelled { if !edge.isEmpty { settle(edge) }; keep() }
    }
    @objc private func togglePlayerSize() {
        guard let host = superview, tuckedSide == 0 else { return }
        let big = frame.width > min(host.bounds.width * 0.6, 620)
        let w = big ? (kind == "youtube" ? 356 + 2 * StandMediaFloat.pad : minW) : min(host.bounds.width * 0.7, 760)
        let h = kind == "youtube" ? naturalH(w) : frame.height
        UIView.animate(withDuration: 0.25) { self.frame = self.fitted(CGRect(x: self.frame.maxX - w, y: self.frame.maxY - h, width: w, height: h), in: host) }
        if !edge.isEmpty { settle(edge) }
        keep()
    }
    @objc private func hideTapped() {
        guard let host = superview else { return }
        tuck(frame.midX < host.bounds.midX ? -1 : 1)
    }
    private func tuck(_ side: CGFloat) {
        guard let host = superview else { return }
        shown = frame; shownEdge = edge
        tuckedSide = side
        // (put away, it leaves the music the whole screen)
        if !edge.isEmpty { let e = edge; setEdge(""); UserDefaults.standard.set(e, forKey: "standMediaEdge") }
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
        if !shownEdge.isEmpty { settle(shownEdge) }
    }
    func hostResized() {
        guard let host = superview, tuckedSide == 0 else { return }
        frame = fitted(frame, in: host)
        // (turned to a phone's width: beside the music becomes under it)
        if !edge.isEmpty { settle(edge, animated: false) }
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
