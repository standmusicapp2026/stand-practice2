import UIKit
import AVFoundation
import Vision
import CoreImage

/// The page scanner. A live view with the page outlined. When the page has been held still for
/// seven tenths of a second a ring fills and the page is captured by itself; the shutter button does it at once.
/// Each page is straightened (perspective) and saved as a JPEG; the web review then cleans it.
final class PageScanner: UIViewController, AVCapturePhotoCaptureDelegate, AVCaptureVideoDataOutputSampleBufferDelegate {
    var onFinish: (([URL]) -> Void)?

    static var available: Bool {
        AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) != nil
    }

    private let session = AVCaptureSession()
    private let sessionQueue = DispatchQueue(label: "stand.scan.session")
    private let videoQueue = DispatchQueue(label: "stand.scan.video")
    private let stillOutput = AVCapturePhotoOutput()
    private let videoOutput = AVCaptureVideoDataOutput()
    private lazy var preview = AVCaptureVideoPreviewLayer(session: session)

    private let outline = CAShapeLayer()
    private let ring = CAShapeLayer()
    private let flash = UIView()
    private let hint = UILabel()
    private let counter = UILabel()
    private let shutter = UIButton(type: .custom)
    private let closeButton = UIButton(type: .custom)
    private let doneButton = UIButton(type: .system)

    // detection state (main queue)
    private var quad: [CGPoint]?                 // page corners, upright, normalized, TL TR BR BL
    private var imageSize = CGSize(width: 3, height: 4)
    private var stableSince: CFTimeInterval?
    private var noPageSince: CFTimeInterval?
    private var lastCaptured: [CGPoint]?
    private var captureCooldown: CFTimeInterval = 0
    private var inFlight = false

    // detection runs on the video queue; these are only touched there
    private var lastFrame: CFTimeInterval = 0

    private let work = DispatchGroup()
    private var pages: [URL] = []

    private static let ciContext = CIContext()
    /// the pages taken, made ready one after another (their order kept)
    private static let making = DispatchQueue(label: "stand.scan.making", qos: .userInitiated)

    // MARK: view

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        preview.videoGravity = .resizeAspectFill
        view.layer.addSublayer(preview)

        outline.fillColor = UIColor.clear.cgColor
        outline.strokeColor = UIColor(red: 0.45, green: 0.95, blue: 0.65, alpha: 1).cgColor
        outline.lineWidth = 3
        outline.lineJoin = .round
        view.layer.addSublayer(outline)

        ring.frame = CGRect(x: 0, y: 0, width: 80, height: 80)
        ring.path = UIBezierPath(arcCenter: CGPoint(x: 40, y: 40), radius: 34, startAngle: -.pi / 2, endAngle: 1.5 * .pi, clockwise: true).cgPath
        ring.fillColor = UIColor.clear.cgColor
        ring.strokeColor = UIColor.white.cgColor
        ring.lineWidth = 5
        ring.lineCap = .round
        ring.strokeEnd = 0
        view.layer.addSublayer(ring)

        let symbol = UIImage(systemName: "xmark", withConfiguration: UIImage.SymbolConfiguration(pointSize: 16, weight: .semibold))
        closeButton.setImage(symbol, for: .normal)
        closeButton.tintColor = .white
        closeButton.backgroundColor = UIColor.black.withAlphaComponent(0.45)
        closeButton.layer.cornerRadius = 20
        closeButton.accessibilityLabel = "Close scanner"
        closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
        view.addSubview(closeButton)

        doneButton.setTitle("Done", for: .normal)
        doneButton.titleLabel?.font = .systemFont(ofSize: 17, weight: .semibold)
        doneButton.tintColor = .white
        doneButton.isEnabled = false
        doneButton.addTarget(self, action: #selector(doneTapped), for: .touchUpInside)
        view.addSubview(doneButton)

        hint.text = "Show a page to scan"
        hint.textColor = .white
        hint.font = .systemFont(ofSize: 15, weight: .semibold)
        hint.textAlignment = .center
        hint.backgroundColor = UIColor.black.withAlphaComponent(0.45)
        hint.layer.cornerRadius = 14
        hint.clipsToBounds = true
        view.addSubview(hint)

        counter.textColor = .white
        counter.font = .systemFont(ofSize: 14, weight: .semibold)
        counter.textAlignment = .center
        counter.isHidden = true
        view.addSubview(counter)

        shutter.backgroundColor = .white
        shutter.layer.borderWidth = 5
        shutter.layer.borderColor = UIColor(white: 0.85, alpha: 1).cgColor
        shutter.accessibilityLabel = "Scan this page"
        shutter.addTarget(self, action: #selector(shutterTapped), for: .touchUpInside)
        view.addSubview(shutter)

        flash.backgroundColor = .white
        flash.alpha = 0
        flash.isUserInteractionEnabled = false
        view.addSubview(flash)
    }

    override var prefersStatusBarHidden: Bool { true }
    override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .portrait }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        preview.frame = view.bounds
        let top = view.safeAreaInsets.top + 8
        let bottom = view.safeAreaInsets.bottom
        closeButton.frame = CGRect(x: 16, y: top, width: 40, height: 40)
        let dw = doneButton.sizeThatFits(.zero).width + 8
        doneButton.frame = CGRect(x: view.bounds.width - dw - 16, y: top, width: dw, height: 40)
        let hw = min(view.bounds.width - 140, 340)
        hint.frame = CGRect(x: (view.bounds.width - hw) / 2, y: top + 52, width: hw, height: 30)
        shutter.frame = CGRect(x: (view.bounds.width - 76) / 2, y: view.bounds.height - bottom - 40 - 76, width: 76, height: 76)
        shutter.layer.cornerRadius = 38
        counter.frame = CGRect(x: 0, y: shutter.frame.minY - 30, width: view.bounds.width, height: 22)
        flash.frame = view.bounds
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        AVCaptureDevice.requestAccess(for: .video) { ok in
            DispatchQueue.main.async {
                if ok { self.startSession() } else { self.fail("Stand needs the camera to scan pages. You can allow it in Settings.") }
            }
        }
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        sessionQueue.async { if self.session.isRunning { self.session.stopRunning() } }
    }

    // MARK: camera

    private func startSession() {
        sessionQueue.async {
            guard !self.session.isRunning, self.session.inputs.isEmpty else { return }
            self.session.beginConfiguration()
            self.session.sessionPreset = .photo
            guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
                  let input = try? AVCaptureDeviceInput(device: device), self.session.canAddInput(input) else {
                self.session.commitConfiguration()
                DispatchQueue.main.async { self.fail("No camera was found.") }
                return
            }
            self.session.addInput(input)
            if self.session.canAddOutput(self.stillOutput) { self.session.addOutput(self.stillOutput) }
            // (the sharpest, biggest photo the camera can take: small print and bar numbers stay readable)
            self.stillOutput.maxPhotoQualityPrioritization = .quality
            if #available(iOS 16.0, *), let biggest = device.activeFormat.supportedMaxPhotoDimensions.max(by: { $0.width * $0.height < $1.width * $1.height }) {
                self.stillOutput.maxPhotoDimensions = biggest
            }
            self.videoOutput.alwaysDiscardsLateVideoFrames = true
            self.videoOutput.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
            self.videoOutput.setSampleBufferDelegate(self, queue: self.videoQueue)
            if self.session.canAddOutput(self.videoOutput) { self.session.addOutput(self.videoOutput) }
            self.session.commitConfiguration()

            if (try? device.lockForConfiguration()) != nil {
                if device.isFocusModeSupported(.continuousAutoFocus) { device.focusMode = .continuousAutoFocus }
                // (a page is close: focus is looked for near first, and found sooner)
                if device.isAutoFocusRangeRestrictionSupported { device.autoFocusRangeRestriction = .near }
                if device.isSmoothAutoFocusSupported { device.isSmoothAutoFocusEnabled = false }
                if device.isExposureModeSupported(.continuousAutoExposure) { device.exposureMode = .continuousAutoExposure }
                device.unlockForConfiguration()
            }
            self.session.startRunning()
            DispatchQueue.main.async { self.setPreviewUpright() }
        }
    }

    private func setPreviewUpright() {
        guard let connection = preview.connection else { return }
        if #available(iOS 17.0, *) {
            if connection.isVideoRotationAngleSupported(90) { connection.videoRotationAngle = 90 }
        } else if connection.isVideoOrientationSupported {
            connection.videoOrientation = .portrait
        }
    }

    // MARK: live detection (video queue)

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        let now = CACurrentMediaTime()
        guard now - lastFrame > 0.2, let pixels = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        lastFrame = now
        let w = CVPixelBufferGetWidth(pixels), h = CVPixelBufferGetHeight(pixels)

        let request = VNDetectDocumentSegmentationRequest()
        let handler = VNImageRequestHandler(cvPixelBuffer: pixels, orientation: .right, options: [:])
        try? handler.perform([request])

        var corners: [CGPoint]?
        if let page = request.results?.first, page.confidence > 0.5,
           page.boundingBox.width * page.boundingBox.height > 0.12 {
            corners = [page.topLeft, page.topRight, page.bottomRight, page.bottomLeft]
        } else {
            // (a page on a light table, or half in shadow: its edges looked for as a rectangle instead)
            let rect = VNDetectRectanglesRequest()
            rect.minimumAspectRatio = 0.45; rect.maximumAspectRatio = 1; rect.minimumSize = 0.35
            rect.minimumConfidence = 0.6; rect.quadratureTolerance = 25; rect.maximumObservations = 1
            try? handler.perform([rect])
            if let r = rect.results?.first, r.boundingBox.width * r.boundingBox.height > 0.15 {
                corners = [r.topLeft, r.topRight, r.bottomRight, r.bottomLeft]
            }
        }
        // upright image: the buffer is turned a quarter turn
        let upright = CGSize(width: h, height: w)
        DispatchQueue.main.async { self.track(corners, upright: upright, now: now) }
    }

    // MARK: steady-page logic (main queue)

    private func track(_ corners: [CGPoint]?, upright: CGSize, now: CFTimeInterval) {
        imageSize = upright
        guard let c = corners else {
            quad = nil
            stableSince = nil
            outline.path = nil
            ring.removeAnimation(forKey: "ring")
            ring.strokeEnd = 0
            if noPageSince == nil { noPageSince = now }
            if let gone = noPageSince, now - gone > 1 { lastCaptured = nil }
            setHint(inFlight ? nil : "Show a page to scan")
            return
        }
        noPageSince = nil

        let moved = quad.map { distance($0, c) } ?? 1
        // (the outline follows the page smoothly, without trembling)
        let shown: [CGPoint] = (quad != nil && moved < 0.08) ? zip(quad!, c).map { CGPoint(x: $0.x * 0.55 + $1.x * 0.45, y: $0.y * 0.55 + $1.y * 0.45) } : c
        quad = shown

        let path = UIBezierPath()
        let points = shown.map(toView)
        path.move(to: points[0])
        for p in points.dropFirst() { path.addLine(to: p) }
        path.close()
        let centre = CGPoint(x: points.map(\.x).reduce(0, +) / 4, y: points.map(\.y).reduce(0, +) / 4)
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        outline.path = path.cgPath
        ring.position = centre
        CATransaction.commit()

        if moved > 0.02 || stableSince == nil {
            stableSince = now
            ring.removeAnimation(forKey: "ring")
            ring.strokeEnd = 0
            let grow = CABasicAnimation(keyPath: "strokeEnd")
            grow.fromValue = 0
            grow.toValue = 1
            grow.duration = 0.7
            grow.timingFunction = CAMediaTimingFunction(name: .linear)
            grow.fillMode = .forwards
            grow.isRemovedOnCompletion = false
            ring.add(grow, forKey: "ring")
        }

        let steady = now - (stableSince ?? now)
        let isNewPage = lastCaptured.map { distance($0, c) > 0.06 } ?? true
        if steady >= 0.7, now > captureCooldown, isNewPage, !inFlight {
            lastCaptured = c
            captureCooldown = now + 1.0
            shoot()
            return
        }
        if !isNewPage && !inFlight {
            setHint("Got it. Turn the page for the next one")
        } else {
            setHint(steady > 0.25 ? "Hold still…" : "Page found")
        }
    }

    private func setHint(_ text: String?) {
        guard let text else { return }
        if hint.text != text { hint.text = text }
    }

    // MARK: capture

    @objc private func shutterTapped() {
        shoot()
    }

    private func shoot() {
        guard !inFlight, session.isRunning else { return }
        inFlight = true
        work.enter()
        shotFrom = outline.path?.boundingBox
        shotQuad = quad
        flashNow()
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        let settings = AVCapturePhotoSettings(format: [AVVideoCodecKey: AVVideoCodecType.jpeg])
        if #available(iOS 16.0, *) { settings.maxPhotoDimensions = stillOutput.maxPhotoDimensions }
        settings.photoQualityPrioritization = .balanced
        stillOutput.capturePhoto(with: settings, delegate: self)
    }

    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        let data = error == nil ? photo.fileDataRepresentation() : nil
        let hint = shotQuad
        // (the next page can be taken at once: the one just taken is made ready meanwhile, the pages
        // one after another in the order they were taken)
        DispatchQueue.main.async { self.inFlight = false }
        PageScanner.making.async {
            let url = data.flatMap { PageScanner.straighten($0, hint: hint) }
            DispatchQueue.main.async {
                if let url {
                    self.pages.append(url)
                    self.showPage(url)
                    self.counter.isHidden = false
                    self.counter.text = self.pages.count == 1 ? "1 page" : "\(self.pages.count) pages"
                    self.doneButton.isEnabled = true
                    self.setHint("Got it. Turn the page for the next one")
                }
                self.work.leave()
            }
        }
    }

    /// Straightens the page (perspective), keeps it sharp and writes a JPEG into the incoming folder.
    private static func straighten(_ data: Data, hint: [CGPoint]? = nil) -> URL? {
        guard var image = CIImage(data: data, options: [.applyOrientationProperty: true]) else { return nil }
        let box = image.extent
        let request = VNDetectDocumentSegmentationRequest()
        let handler = VNImageRequestHandler(ciImage: image, options: [:])
        try? handler.perform([request])
        var found: VNRectangleObservation? = request.results?.first.flatMap { $0.confidence > 0.3 ? $0 : nil }
        // (the outline seen on the screen a moment before is the page too: when the photo's own finding
        // is much smaller than it — a part of the page taken for all of it — the outline is kept)
        var corners: [CGPoint]? = found.map { [$0.topLeft, $0.topRight, $0.bottomRight, $0.bottomLeft] }
        if let h = hint, h.count == 4 {
            func area(_ q: [CGPoint]) -> CGFloat {
                var a: CGFloat = 0
                for i in 0..<4 { let p = q[i], n = q[(i + 1) % 4]; a += p.x * n.y - n.x * p.y }
                return abs(a) / 2
            }
            if let c = corners, area(c) >= area(h) * 0.8 { } else if area(h) > 0.12 { corners = h; found = nil }
        }
        if corners == nil {
            // (the page's edges as a rectangle, when the page itself was not made out)
            let rect = VNDetectRectanglesRequest()
            rect.minimumAspectRatio = 0.45; rect.maximumAspectRatio = 1; rect.minimumSize = 0.35
            rect.minimumConfidence = 0.6; rect.quadratureTolerance = 25; rect.maximumObservations = 1
            try? handler.perform([rect])
            found = rect.results?.first
            corners = found.map { [$0.topLeft, $0.topRight, $0.bottomRight, $0.bottomLeft] }
        }
        var flat = false
        if let page = corners, page.count == 4,
           let filter = CIFilter(name: "CIPerspectiveCorrection") {
            func at(_ p: CGPoint) -> CIVector {
                CIVector(x: box.minX + p.x * box.width, y: box.minY + p.y * box.height)
            }
            filter.setValue(image, forKey: kCIInputImageKey)
            filter.setValue(at(page[0]), forKey: "inputTopLeft")
            filter.setValue(at(page[1]), forKey: "inputTopRight")
            filter.setValue(at(page[3]), forKey: "inputBottomLeft")
            filter.setValue(at(page[2]), forKey: "inputBottomRight")
            if let out = filter.outputImage { image = out; flat = true }
        }
        let longest = max(image.extent.width, image.extent.height)
        let k = min(1, 3200 / longest)
        if k < 1 { image = image.transformed(by: CGAffineTransform(scaleX: k, y: k)) }
        guard let jpeg = ciContext.jpegRepresentation(
            of: image,
            colorSpace: CGColorSpaceCreateDeviceRGB(),
            options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: 0.92]
        ) else { return nil }
        // (a page already flattened says so in its name: it is not looked for again in the review)
        let url = incomingDir.appendingPathComponent(UUID().uuidString + (flat ? "-flat.jpg" : "-scan.jpg"))
        do { try jpeg.write(to: url); return url } catch { return nil }
    }

    // The page just scanned, straightened, pops up small in the middle for a moment (to see that it
    // came out well), then flies down to the page count and is gone.
    private var shotFrom: CGRect?
    /// the page's corners as outlined on the screen when the photo was taken (upright, normalized,
    /// origin at the bottom left, TL TR BR BL): used when the photo itself does not show the page clearly
    private var shotQuad: [CGPoint]?
    private func showPage(_ url: URL) {
        guard let img = UIImage(contentsOfFile: url.path), img.size.width > 0 else { return }
        let b = view.bounds
        let s = min(b.width * 0.46 / img.size.width, b.height * 0.42 / img.size.height)
        let size = CGSize(width: img.size.width * s, height: img.size.height * s)
        let mid = CGRect(x: (b.width - size.width) / 2, y: (b.height - size.height) / 2 - 20, width: size.width, height: size.height)
        let card = UIView(frame: shotFrom.flatMap { $0.width > 20 ? $0 : nil } ?? mid.insetBy(dx: size.width * 0.3, dy: size.height * 0.3))
        card.layer.shadowColor = UIColor.black.cgColor; card.layer.shadowOpacity = 0.45; card.layer.shadowRadius = 18; card.layer.shadowOffset = CGSize(width: 0, height: 8)
        card.isUserInteractionEnabled = false
        let iv = UIImageView(image: img)
        iv.frame = card.bounds; iv.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        iv.contentMode = .scaleAspectFill; iv.clipsToBounds = true
        iv.layer.cornerRadius = 8; iv.layer.borderWidth = 3; iv.layer.borderColor = UIColor.white.cgColor
        card.addSubview(iv)
        view.insertSubview(card, belowSubview: flash)
        card.alpha = 0.2
        UIView.animate(withDuration: 0.42, delay: 0, usingSpringWithDamping: 0.72, initialSpringVelocity: 0.6, options: [.curveEaseOut]) {
            card.frame = mid; card.alpha = 1
            card.transform = CGAffineTransform(rotationAngle: -0.035)
        } completion: { _ in
            UIView.animate(withDuration: 0.5, delay: 1.0, options: [.curveEaseIn]) {
                let end = self.counter.isHidden ? CGPoint(x: b.midX, y: b.maxY - 140) : self.counter.center
                card.center = end
                card.transform = CGAffineTransform(scaleX: 0.12, y: 0.12).rotated(by: -0.2)
                card.alpha = 0
            } completion: { _ in card.removeFromSuperview() }
        }
        // (a gentle tick when the page is kept)
        UINotificationFeedbackGenerator().notificationOccurred(.success)
    }

    private func flashNow() {
        flash.layer.removeAllAnimations()
        flash.alpha = 0.6
        UIView.animate(withDuration: 0.35) { self.flash.alpha = 0 }
    }

    // MARK: leaving

    @objc private func closeTapped() {
        if pages.isEmpty {
            finish(keep: false)
            return
        }
        let alert = UIAlertController(title: "Leave the scanner?",
                                      message: "The \(pages.count) scanned page\(pages.count == 1 ? "" : "s") will be thrown away.",
                                      preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Keep scanning", style: .cancel))
        alert.addAction(UIAlertAction(title: "Discard", style: .destructive) { _ in self.finish(keep: false) })
        present(alert, animated: true)
    }

    @objc private func doneTapped() {
        doneButton.isEnabled = false
        // wait for a capture that is still being straightened
        work.notify(queue: .main) { self.finish(keep: true) }
    }

    private func finish(keep: Bool) {
        sessionQueue.async { if self.session.isRunning { self.session.stopRunning() } }
        let result = keep ? pages : []
        if !keep { pages.forEach { try? FileManager.default.removeItem(at: $0) } }
        dismiss(animated: true) {
            if keep && !result.isEmpty { self.onFinish?(result) }
        }
    }

    private func fail(_ message: String) {
        let alert = UIAlertController(title: "Scanner", message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in self.finish(keep: false) })
        present(alert, animated: true)
    }

    // MARK: geometry

    /// Upright normalized point (origin bottom-left) to a point on screen, matching the aspect-fill preview.
    private func toView(_ n: CGPoint) -> CGPoint {
        let b = view.bounds.size
        let s = max(b.width / imageSize.width, b.height / imageSize.height)
        let dw = imageSize.width * s, dh = imageSize.height * s
        return CGPoint(x: (b.width - dw) / 2 + n.x * dw, y: (b.height - dh) / 2 + (1 - n.y) * dh)
    }

    private func distance(_ a: [CGPoint], _ b: [CGPoint]) -> CGFloat {
        zip(a, b).map { p in hypot(p.0.x - p.1.x, p.0.y - p.1.y) }.max() ?? 1
    }
}
