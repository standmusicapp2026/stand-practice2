import UIKit
import AVFoundation
import PhotosUI
import UniformTypeIdentifiers
import CoreImage

// Videos in and out of Stand at their own quality.
//
// In:  a video from Photos (the original file, never made smaller on the way) or from Files is
//      copied into Stand, and its sound is taken out on its own (for the waveform and for following
//      the playing). The web view's own file picker is not used: it could fail on big or long videos.
// Out: Studio draws each picture of the finished video (the video with the score over it) and hands
//      it here; the pictures are made into an H.264 film at the video's own frame rate, and the
//      sound is the original's (only made louder if Studio levels it), or the one Studio made.
//
// Page → app:
//   standVideoIn  { cmd: "pick", from: "photos" | "files" } · { cmd: "test", path } (self test: a file in the app)
//   standVideoOut { op: "begin", id, w, h, fps, bitrate } · { op: "frame", id, i, data } (JPEG, base64)
//                 · { op: "src", id, part: "begin" | "chunk" | "end", data, name } (the original video)
//                 · { op: "wav", id, part: "begin" | "chunk" | "end", data } (the sound made by Studio)
//                 · { op: "end", id, audio: "src" | "wav" | "none", a, b, gain } · { op: "cancel", id }
//                 · { op: "over", id, a, b, fps, w, h, crop: [x, y, w, h] } then { op: "oframe", id, i, data, rect }:
//                   only what Studio draws over the video (PNG, see-through), put over the original
//                   video itself at its own size (never drawn again by the page: nothing is lost)
// App → page:
//   standVideoInEvent({ type: "busy" | "done" | "error" | "cancel", video, audio, name, dur, w, h, fps, message })
//   standVideoOutEvent({ id, type: "ready" | "ack" | "src" | "progress" | "done" | "error", i, fps, w, h, hasAudio, path, f, message })

final class StandVideoKit: NSObject, PHPickerViewControllerDelegate, UIDocumentPickerDelegate {
    static let shared = StandVideoKit()
    var send: ((String, [String: Any]) -> Void)?

    // MARK: in

    func pick(from: String, on host: UIViewController, at rect: CGRect? = nil, labels: [String] = []) {
        if from == "ask" {
            // (as iOS asks everywhere: Photos or Files, in its own menu by the button)
            let sheet = UIAlertController(title: nil, message: nil, preferredStyle: .actionSheet)
            sheet.addAction(UIAlertAction(title: labels.count > 0 ? labels[0] : "Photo Library", style: .default) { _ in self.pick(from: "photos", on: host) })
            sheet.addAction(UIAlertAction(title: labels.count > 1 ? labels[1] : "Choose File", style: .default) { _ in self.pick(from: "files", on: host) })
            sheet.addAction(UIAlertAction(title: labels.count > 2 ? labels[2] : "Cancel", style: .cancel) { _ in self.inEvent(["type": "cancel"]) })
            if let pop = sheet.popoverPresentationController {
                pop.sourceView = host.view
                pop.sourceRect = rect ?? CGRect(x: host.view.bounds.midX, y: host.view.bounds.midY, width: 1, height: 1)
                pop.permittedArrowDirections = rect == nil ? [] : [.up, .down]
            }
            host.present(sheet, animated: true)
            return
        }
        if from == "files" {
            let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.movie, .video, .mpeg4Movie, .quickTimeMovie], asCopy: true)
            picker.delegate = self
            picker.allowsMultipleSelection = false
            host.present(picker, animated: true)
            return
        }
        var config = PHPickerConfiguration()
        config.filter = .videos
        config.selectionLimit = 1
        // the file as it is in Photos (HEVC, 4K, 60 fps…), not a smaller copy made for "compatibility"
        config.preferredAssetRepresentationMode = .current
        let picker = PHPickerViewController(configuration: config)
        picker.delegate = self
        host.present(picker, animated: true)
    }

    func picker(_ picker: PHPickerViewController, didFinishPicking results: [PHPickerResult]) {
        picker.dismiss(animated: true)
        guard let item = results.first?.itemProvider else { inEvent(["type": "cancel"]); return }
        let type = item.registeredTypeIdentifiers.first { UTType($0)?.conforms(to: .movie) == true } ?? UTType.movie.identifier
        inEvent(["type": "busy"])
        let name = item.suggestedName ?? "Video"
        item.loadFileRepresentation(forTypeIdentifier: type) { [weak self] url, error in
            guard let self = self else { return }
            guard let url = url else { self.inEvent(["type": "error", "message": error?.localizedDescription ?? "no file"]); return }
            // (the file given here is gone when this returns: copied first)
            let ext = url.pathExtension.isEmpty ? "mov" : url.pathExtension.lowercased()
            let dest = incomingDir.appendingPathComponent("imp-" + UUID().uuidString + "." + ext)
            do { try FileManager.default.copyItem(at: url, to: dest) } catch {
                self.inEvent(["type": "error", "message": error.localizedDescription]); return
            }
            self.bringIn(dest, name: name)
        }
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        guard let url = urls.first else { inEvent(["type": "cancel"]); return }
        inEvent(["type": "busy"])
        let secured = url.startAccessingSecurityScopedResource()
        defer { if secured { url.stopAccessingSecurityScopedResource() } }
        let ext = url.pathExtension.isEmpty ? "mov" : url.pathExtension.lowercased()
        let dest = incomingDir.appendingPathComponent("imp-" + UUID().uuidString + "." + ext)
        do { try FileManager.default.copyItem(at: url, to: dest) } catch {
            inEvent(["type": "error", "message": error.localizedDescription]); return
        }
        bringIn(dest, name: url.deletingPathExtension().lastPathComponent)
    }
    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) { inEvent(["type": "cancel"]) }

    // (the self test: a video kept in the app, brought in the same way)
    func bringInForTest(_ path: String) {
        let src = URL(fileURLWithPath: path)
        let dest = incomingDir.appendingPathComponent("imp-" + UUID().uuidString + "." + (src.pathExtension.isEmpty ? "mov" : src.pathExtension))
        inEvent(["type": "busy"])
        do { try FileManager.default.copyItem(at: src, to: dest) } catch { inEvent(["type": "error", "message": error.localizedDescription]); return }
        bringIn(dest, name: src.deletingPathExtension().lastPathComponent)
    }

    private func bringIn(_ file: URL, name: String) {
        let asset = AVURLAsset(url: file)
        var msg: [String: Any] = ["type": "done", "video": "/__incoming/" + file.lastPathComponent, "name": name]
        let dur = CMTimeGetSeconds(asset.duration)
        if dur.isFinite { msg["dur"] = dur }
        if let track = asset.tracks(withMediaType: .video).first {
            let size = track.naturalSize.applying(track.preferredTransform)
            msg["w"] = Int(abs(size.width)); msg["h"] = Int(abs(size.height)); msg["fps"] = Double(track.nominalFrameRate)
        }
        guard !asset.tracks(withMediaType: .audio).isEmpty,
              let export = AVAssetExportSession(asset: asset, presetName: AVAssetExportPresetAppleM4A) else {
            StandLog.write("video in: \(name), no sound")
            inEvent(msg); return
        }
        // the sound on its own (the page draws its waveform and follows the playing in it)
        let audioURL = file.deletingPathExtension().appendingPathExtension("m4a")
        export.outputURL = audioURL
        export.outputFileType = .m4a
        export.exportAsynchronously { [weak self] in
            if export.status == .completed { msg["audio"] = "/__incoming/" + audioURL.lastPathComponent }
            else { StandLog.write("video in: sound not taken out: " + (export.error?.localizedDescription ?? "?")) }
            self?.inEvent(msg)
        }
    }

    private func inEvent(_ msg: [String: Any]) {
        DispatchQueue.main.async { self.send?("standVideoInEvent", msg) }
    }

    // MARK: out

    private final class Job {
        let id: String
        let w: Int, h: Int
        var fps: Int
        var rate: Int
        let url: URL
        var writer: AVAssetWriter?
        var input: AVAssetWriterInput?
        var adaptor: AVAssetWriterInputPixelBufferAdaptor?
        var src: (FileHandle, URL)?
        var wav: (FileHandle, URL)?
        var frames = 0
        var failed = false
        var lastPts: CMTime = .negativeInfinity
        var over: Over?
        init(id: String, w: Int, h: Int, fps: Int, rate: Int, url: URL) {
            self.id = id; self.w = w; self.h = h; self.fps = fps; self.rate = rate; self.url = url
        }
    }
    // The music over the original video: the pictures Studio draws (see-through) wait here, by number,
    // until the video's own frames reach them; the film is made by iOS from the original, at its size.
    private final class Over {
        let cond = NSCondition()
        var frames: [Int: CIImage] = [:]
        var got = 0          // (pictures received: 0 … got-1)
        var used = 0         // (the last one used)
        var jsDone = false
        var cancelled = false
        var exported: Bool?  // (nil: still being made; then whether it worked)
        var error: String?
        var endBody: [String: Any]?
        var session: AVAssetExportSession?
        let fps: Double, w: Int, h: Int
        init(fps: Double, w: Int, h: Int) { self.fps = fps; self.w = w; self.h = h }
    }
    private lazy var ci = CIContext(options: [.cacheIntermediates: false])
    private var jobs: [String: Job] = [:]
    private let queue = DispatchQueue(label: "stand.videoout")

    func out(_ body: [String: Any]) {
        let id = body["id"] as? String ?? ""
        let op = body["op"] as? String ?? ""
        // (the pictures are big: decoded and written away from the main thread, in order)
        queue.async { [weak self] in self?.outOn(op, id, body) }
    }

    private func outOn(_ op: String, _ id: String, _ body: [String: Any]) {
        switch op {
        case "begin":
            // (the film itself is started with the first picture: the frame rate may still change,
            // once the original video has been looked at)
            let w = max(16, (body["w"] as? Int ?? 1080) / 2 * 2), h = max(16, (body["h"] as? Int ?? 1920) / 2 * 2)
            let fps = min(120, max(1, body["fps"] as? Int ?? 30))
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("studio-" + UUID().uuidString + ".mp4")
            jobs[id] = Job(id: id, w: w, h: h, fps: fps, rate: body["bitrate"] as? Int ?? 0, url: url)
            outEvent(id, ["type": "ready", "w": w, "h": h, "fps": fps])
        case "set":
            guard let job = jobs[id], job.writer == nil else { return }
            if let f = body["fps"] as? Int { job.fps = min(120, max(1, f)) }
            outEvent(id, ["type": "ready", "w": job.w, "h": job.h, "fps": job.fps])
        case "frame":
            guard let job = jobs[id], !job.failed else { outEvent(id, ["type": "error", "message": "no job"]); return }
            if job.writer == nil, let err = startWriter(job) { outEvent(id, ["type": "error", "message": err]); return }
            guard let input = job.input, let adaptor = job.adaptor else { return }
            let i = body["i"] as? Int ?? job.frames
            guard let b64 = body["data"] as? String, let data = Data(base64Encoded: b64), let image = UIImage(data: data)?.cgImage else {
                outEvent(id, ["type": "error", "message": "picture \(i)"]); return
            }
            autoreleasepool {
                guard let pool = adaptor.pixelBufferPool else { job.failed = true; return }
                var pb: CVPixelBuffer?
                CVPixelBufferPoolCreatePixelBuffer(nil, pool, &pb)
                guard let buffer = pb else { job.failed = true; return }
                CVPixelBufferLockBaseAddress(buffer, [])
                let ctx = CGContext(data: CVPixelBufferGetBaseAddress(buffer), width: job.w, height: job.h, bitsPerComponent: 8,
                                    bytesPerRow: CVPixelBufferGetBytesPerRow(buffer), space: CGColorSpaceCreateDeviceRGB(),
                                    bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue)
                ctx?.interpolationQuality = .high
                ctx?.draw(image, in: CGRect(x: 0, y: 0, width: job.w, height: job.h))
                CVPixelBufferUnlockBaseAddress(buffer, [])
                // (at its own moment in the video when the page says it, so the film keeps the video's timing)
                let pts = (body["t"] as? Double).map { CMTime(seconds: max(0, $0), preferredTimescale: 6000) } ?? CMTime(value: CMTimeValue(i), timescale: CMTimeScale(job.fps))
                guard CMTimeCompare(pts, job.lastPts) > 0 else { return }
                // (iOS may take a while with the pictures before it: waited for, never forced — appending
                // when it is not ready ends the app)
                var waited = 0
                while !input.isReadyForMoreMediaData && waited < 12000 && job.writer?.status == .writing { usleep(5000); waited += 1 }
                guard input.isReadyForMoreMediaData else { job.failed = true; return }
                if adaptor.append(buffer, withPresentationTime: pts) { job.lastPts = pts } else { job.failed = true }
            }
            if job.failed { outEvent(id, ["type": "error", "message": job.writer?.error?.localizedDescription ?? "frame \(i)"]); return }
            job.frames = i + 1
            outEvent(id, ["type": "ack", "i": i])
        case "src", "wav":
            guard let job = jobs[id] else { outEvent(id, ["type": "error", "message": "no job"]); return }
            switch body["part"] as? String {
            case "begin":
                let ext = op == "wav" ? "wav" : ((body["name"] as? String).map { URL(fileURLWithPath: $0).pathExtension }.flatMap { $0.isEmpty ? nil : $0 } ?? "mov")
                let url = FileManager.default.temporaryDirectory.appendingPathComponent("studio-" + op + "-" + UUID().uuidString + "." + ext)
                FileManager.default.createFile(atPath: url.path, contents: nil)
                guard let hnd = try? FileHandle(forWritingTo: url) else { outEvent(id, ["type": "error", "message": "open"]); return }
                if op == "wav" { job.wav = (hnd, url) } else { job.src = (hnd, url) }
                outEvent(id, ["type": "chunk"])
            case "chunk":
                guard let e = op == "wav" ? job.wav : job.src, let b64 = body["data"] as? String, let data = Data(base64Encoded: b64) else { outEvent(id, ["type": "error", "message": "chunk"]); return }
                do { try e.0.write(contentsOf: data) } catch { outEvent(id, ["type": "error", "message": "There is not enough space on this device"]); return }
                outEvent(id, ["type": "chunk"])
            default:
                guard let e = op == "wav" ? job.wav : job.src else { return }
                try? e.0.close()
                if op == "src" {
                    // what the original is: its frame rate and size, and whether it has sound
                    let asset = AVURLAsset(url: e.1)
                    var info: [String: Any] = ["type": "src", "hasAudio": !asset.tracks(withMediaType: .audio).isEmpty]
                    if let t = asset.tracks(withMediaType: .video).first {
                        info["fps"] = Double(t.nominalFrameRate)
                        let s = t.naturalSize.applying(t.preferredTransform); info["w"] = Int(abs(s.width)); info["h"] = Int(abs(s.height))
                    }
                    outEvent(id, info)
                } else { outEvent(id, ["type": "chunk"]) }
            }
        case "end":
            if let job = jobs[id], let ov = job.over {
                jobs.removeValue(forKey: id)
                ov.cond.lock(); ov.jsDone = true; ov.endBody = body; ov.cond.broadcast()
                let ready = ov.exported != nil
                ov.cond.unlock()
                // (the film may still be being made: it goes on when it is)
                if ready { overDone(id, job) }
                return
            }
            guard let job = jobs.removeValue(forKey: id), let writer = job.writer, let input = job.input else { outEvent(id, ["type": "error", "message": "no pictures"]); return }
            input.markAsFinished()
            // (the last picture lasts until the end of the part)
            if let d = body["dur"] as? Double, d > 0, CMTimeCompare(CMTime(seconds: d, preferredTimescale: 6000), job.lastPts) > 0 { writer.endSession(atSourceTime: CMTime(seconds: d, preferredTimescale: 6000)) }
            let audio = body["audio"] as? String ?? "none"
            let a = body["a"] as? Double ?? 0, b = body["b"] as? Double ?? 0
            let gain = Float(body["gain"] as? Double ?? 1)
            writer.finishWriting { [weak self] in
                guard let self = self else { return }
                guard writer.status == .completed else {
                    self.outEvent(id, ["type": "error", "message": writer.error?.localizedDescription ?? "finish"]); self.clean(job); return
                }
                // ("mix": the original sound, as it is, with the room Studio adds laid over it)
                let fromSrc = audio == "src" || audio == "mix"
                let sound: URL? = fromSrc ? job.src?.1 : audio == "wav" ? job.wav?.1 : nil
                if let sound = sound {
                    self.outEvent(id, ["type": "progress", "f": 0.97])
                    self.addSound(to: job.url, from: sound, range: fromSrc ? (a, b) : nil, gain: fromSrc ? gain : 1, wet: audio == "mix" ? job.wav?.1 : nil) { final, err in
                        if let final = final { self.finished(id, final, job) }
                        else {
                            // (the film without its sound is no use: said plainly, the page falls back)
                            StandLog.write("studio out: sound failed: " + (err ?? "?"))
                            self.outEvent(id, ["type": "error", "message": err ?? "sound"]); self.clean(job)
                        }
                    }
                } else { self.finished(id, job.url, job) }
            }
        case "cut":
            // A recording cut (the part kept, or what is left around the part taken out): the pictures
            // and the sound copied as they are, never made again, so nothing is lost, and at once.
            guard let job = jobs.removeValue(forKey: id), let src = job.src?.1 else { outEvent(id, ["type": "error", "message": "no video"]); return }
            let segs = (body["segs"] as? [[Double]]) ?? []
            let asset = AVURLAsset(url: src)
            let comp = AVMutableComposition()
            var at = CMTime.zero
            do {
                for sg in segs where sg.count == 2 && sg[1] > sg[0] {
                    let r = CMTimeRange(start: CMTime(seconds: sg[0], preferredTimescale: 6000), end: CMTime(seconds: sg[1], preferredTimescale: 6000))
                    try comp.insertTimeRange(r, of: asset, at: at)
                    at = CMTimeAdd(at, r.duration)
                }
            } catch { outEvent(id, ["type": "error", "message": error.localizedDescription]); clean(job); return }
            // (upright as filmed)
            if let sv = asset.tracks(withMediaType: .video).first, let cv = comp.tracks(withMediaType: .video).first { cv.preferredTransform = sv.preferredTransform }
            let mp4 = src.pathExtension.lowercased() == "mp4"
            guard CMTimeCompare(at, .zero) > 0, let ex = AVAssetExportSession(asset: comp, presetName: AVAssetExportPresetPassthrough) else {
                outEvent(id, ["type": "error", "message": "export"]); clean(job); return
            }
            let out = incomingDir.appendingPathComponent("cut-" + UUID().uuidString + (mp4 ? ".mp4" : ".mov"))
            ex.outputURL = out
            ex.outputFileType = mp4 ? .mp4 : .mov
            ex.exportAsynchronously { [weak self] in
                guard let self = self else { return }
                if ex.status == .completed { self.outEvent(id, ["type": "done", "path": "/__incoming/" + out.lastPathComponent]) }
                else { self.outEvent(id, ["type": "error", "message": ex.error?.localizedDescription ?? "cut"]) }
                self.clean(job)
            }
        case "over":
            guard let job = jobs[id], job.src != nil else { outEvent(id, ["type": "error", "message": "no video"]); return }
            if let err = startOver(job, body) { outEvent(id, ["type": "error", "message": err]) }
            else { outEvent(id, ["type": "ready", "over": true, "w": job.over?.w ?? 0, "h": job.over?.h ?? 0]) }
        case "oframe":
            guard let job = jobs[id], let ov = job.over else { outEvent(id, ["type": "error", "message": "no job"]); return }
            let i = body["i"] as? Int ?? ov.got
            guard let b64 = body["data"] as? String, let data = Data(base64Encoded: b64), let pic = CIImage(data: data) else {
                outEvent(id, ["type": "error", "message": "picture \(i)"]); return
            }
            // where it goes on the film (from the top left, in the film's own points)
            let r = (body["rect"] as? [Double]) ?? [0, 0, Double(ov.w), Double(ov.h)]
            let e = pic.extent
            let placed = pic.transformed(by: CGAffineTransform(translationX: -e.minX, y: -e.minY))
                .transformed(by: CGAffineTransform(scaleX: CGFloat(r[2]) / max(1, e.width), y: CGFloat(r[3]) / max(1, e.height)))
                .transformed(by: CGAffineTransform(translationX: CGFloat(r[0]), y: CGFloat(Double(ov.h) - r[1] - r[3])))
            ov.cond.lock()
            ov.frames[i] = placed; ov.got = max(ov.got, i + 1); ov.cond.broadcast()
            // (never far ahead of the film being made: the pictures waiting are kept few)
            let until = Date().addingTimeInterval(120)
            while ov.frames.count > 48 && !ov.cancelled && ov.exported == nil && Date() < until { _ = ov.cond.wait(until: Date().addingTimeInterval(0.5)) }
            let failed = ov.exported == false ? (ov.error ?? "export") : nil
            ov.cond.unlock()
            if let f = failed { outEvent(id, ["type": "error", "message": f]); return }
            outEvent(id, ["type": "ack", "i": i])
        case "cancel":
            if let job = jobs.removeValue(forKey: id) {
                if let ov = job.over { ov.cond.lock(); ov.cancelled = true; ov.cond.broadcast(); ov.cond.unlock(); ov.session?.cancelExport() }
                job.writer?.cancelWriting(); clean(job)
            }
        default: break
        }
    }

    // The film made by iOS from the original video (the part used, cut and upright as shown in Studio),
    // with Studio's pictures laid over each of its frames.
    private func startOver(_ job: Job, _ body: [String: Any]) -> String? {
        guard let src = job.src?.1 else { return "no video" }
        let asset = AVURLAsset(url: src)
        guard let vt = asset.tracks(withMediaType: .video).first else { return "no pictures" }
        let a = body["a"] as? Double ?? 0, b = body["b"] as? Double ?? asset.duration.seconds
        let fps = max(1, body["fps"] as? Double ?? Double(vt.nominalFrameRate))
        let W = max(16, (body["w"] as? Int ?? 1080) / 2 * 2), H = max(16, (body["h"] as? Int ?? 1920) / 2 * 2)
        let crop = (body["crop"] as? [Double]) ?? []
        let comp = AVMutableComposition()
        guard let ct = comp.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid) else { return "track" }
        do { try ct.insertTimeRange(CMTimeRange(start: CMTime(seconds: a, preferredTimescale: 6000), end: CMTime(seconds: b, preferredTimescale: 6000)), of: vt, at: .zero) }
        catch { return error.localizedDescription }
        let tf = vt.preferredTransform
        ct.preferredTransform = tf
        let nat = vt.naturalSize, up = nat.applying(tf); let upW = abs(up.width), upH = abs(up.height)
        // (how the video is turned to be upright)
        let orient: CGImagePropertyOrientation = {
            switch (Int(tf.a.rounded()), Int(tf.b.rounded()), Int(tf.c.rounded()), Int(tf.d.rounded())) {
            case (0, 1, -1, 0): return .right
            case (0, -1, 1, 0): return .left
            case (-1, 0, 0, -1): return .down
            default: return .up
            }
        }()
        let cx = crop.count == 4 ? crop[0] : 0, cy = crop.count == 4 ? crop[1] : 0
        let cw = crop.count == 4 ? max(2, crop[2]) : Double(upW), ch = crop.count == 4 ? max(2, crop[3]) : Double(upH)
        let ov = Over(fps: fps, w: W, h: H)
        let vc = AVMutableVideoComposition(asset: comp) { [weak ov] req in
            guard let ov = ov else { req.finish(with: NSError(domain: "stand", code: 1)); return }
            let t = req.compositionTime.seconds
            let k = max(0, Int((t * ov.fps + 1e-3).rounded(.down)))
            ov.cond.lock()
            let until = Date().addingTimeInterval(120)
            while ov.got <= k && !ov.jsDone && !ov.cancelled && Date() < until { _ = ov.cond.wait(until: Date().addingTimeInterval(0.5)) }
            var j = min(k, ov.got - 1); while j >= 0 && ov.frames[j] == nil { j -= 1 }
            let pic: CIImage? = j >= 0 ? ov.frames[j] : nil
            if j >= 0 { for key in ov.frames.keys where key < j { ov.frames.removeValue(forKey: key) }; ov.used = j }
            let stop = ov.cancelled
            ov.cond.broadcast(); ov.cond.unlock()
            if stop { req.finish(with: NSError(domain: "stand", code: 2)); return }
            // upright (the picture may come as filmed, or already turned)
            var img = req.sourceImage
            let ex = img.extent
            let isUp = abs(ex.width - upW) < 2 && abs(ex.height - upH) < 2
            if !isUp { img = img.oriented(orient) }
            img = img.transformed(by: CGAffineTransform(translationX: -img.extent.minX, y: -img.extent.minY))
            let Hd = img.extent.height
            let r = CGRect(x: cx, y: Double(Hd) - cy - ch, width: cw, height: ch)
            var base = img.cropped(to: r)
                .transformed(by: CGAffineTransform(translationX: -r.minX, y: -r.minY))
                .transformed(by: CGAffineTransform(scaleX: CGFloat(Double(W) / cw), y: CGFloat(Double(H) / ch)))
            if let pic = pic { base = pic.composited(over: base) }
            req.finish(with: base.cropped(to: CGRect(x: 0, y: 0, width: W, height: H)), context: nil)
        }
        vc.renderSize = CGSize(width: W, height: H)
        let presets = AVAssetExportSession.exportPresets(compatibleWith: comp)
        let preset = presets.contains(AVAssetExportPresetHEVCHighestQuality) ? AVAssetExportPresetHEVCHighestQuality : AVAssetExportPresetHighestQuality
        guard let session = AVAssetExportSession(asset: comp, presetName: preset) else { return "export" }
        session.videoComposition = vc
        session.outputURL = job.url
        session.outputFileType = .mp4
        ov.session = session
        job.over = ov
        let id = job.id
        // (the job is held until the film is made: the page may have finished sending long before)
        session.exportAsynchronously { [weak self] in
            guard let self = self, let ov = job.over else { return }
            ov.cond.lock()
            ov.exported = session.status == .completed
            if session.status != .completed { ov.error = session.error?.localizedDescription ?? "export"; StandLog.write("studio over: " + (ov.error ?? "")) }
            let ended = ov.jsDone
            ov.cond.broadcast(); ov.cond.unlock()
            if ended { self.queue.async { self.overDone(id, job) } }
        }
        return nil
    }
    // the film is made and the page has sent all it had: the sound goes in, as for the other films
    private func overDone(_ id: String, _ job: Job) {
        guard let ov = job.over else { return }
        if ov.exported != true { outEvent(id, ["type": "error", "message": ov.error ?? "export"]); clean(job); return }
        let body = ov.endBody ?? [:]
        let audio = body["audio"] as? String ?? "none"
        let a = body["a"] as? Double ?? 0, b = body["b"] as? Double ?? 0
        let gain = Float(body["gain"] as? Double ?? 1)
        let fromSrc = audio == "src" || audio == "mix"
        let sound: URL? = fromSrc ? job.src?.1 : audio == "wav" ? job.wav?.1 : nil
        guard let snd = sound else { finished(id, job.url, job); return }
        outEvent(id, ["type": "progress", "f": 0.97])
        addSound(to: job.url, from: snd, range: fromSrc ? (a, b) : nil, gain: fromSrc ? gain : 1, wet: audio == "mix" ? job.wav?.1 : nil) { final, err in
            if let final = final { self.finished(id, final, job) }
            else { StandLog.write("studio over: sound failed: " + (err ?? "?")); self.outEvent(id, ["type": "error", "message": err ?? "sound"]); self.clean(job) }
        }
    }

    private func startWriter(_ job: Job) -> String? {
        let w = job.w, h = job.h, fps = job.fps
        // (about 0.25 bit for each point of each picture: 1080×1920 at 30 a second ≈ 16 Mbit/s)
        // (about a third of a bit for each point of each picture: 1080×1920 at 30 a second ≈ 21 Mbit/s,
        // more than the camera itself gives; the video is only made smaller this once)
        let rate = job.rate > 0 ? job.rate : Int(Double(w * h * fps) * 0.34)
        guard let writer = try? AVAssetWriter(outputURL: job.url, fileType: .mp4) else { return "writer" }
        let settings: [String: Any] = [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: w, AVVideoHeightKey: h,
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: max(4_000_000, min(60_000_000, rate)),
                AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
                AVVideoExpectedSourceFrameRateKey: fps,
                AVVideoMaxKeyFrameIntervalKey: fps * 2,
            ] as [String: Any],
        ]
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
        input.expectsMediaDataInRealTime = false
        let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
            kCVPixelBufferWidthKey as String: w, kCVPixelBufferHeightKey as String: h,
            kCVPixelBufferCGImageCompatibilityKey as String: true, kCVPixelBufferCGBitmapContextCompatibilityKey as String: true,
        ])
        guard writer.canAdd(input) else { return "input" }
        writer.add(input)
        guard writer.startWriting() else { return writer.error?.localizedDescription ?? "start" }
        writer.startSession(atSourceTime: .zero)
        job.writer = writer; job.input = input; job.adaptor = adaptor
        return nil
    }

    private func finished(_ id: String, _ file: URL, _ job: Job) {
        let dest = incomingDir.appendingPathComponent("studio-" + UUID().uuidString + ".mp4")
        do { try FileManager.default.moveItem(at: file, to: dest) } catch { outEvent(id, ["type": "error", "message": error.localizedDescription]); clean(job); return }
        clean(job)
        outEvent(id, ["type": "done", "path": "/__incoming/" + dest.lastPathComponent])
    }
    private func clean(_ job: Job) {
        for u in [job.src?.1, job.wav?.1, job.url] { if let u = u { try? FileManager.default.removeItem(at: u) } }
    }

    // The film (pictures only) with its sound: the pictures are copied as they are (never made again),
    // the sound is made into AAC at a high rate from the original (the part used, made louder by
    // `gain` when Studio levels it) or from Studio's own.
    private func addSound(to film: URL, from sound: URL, range: (Double, Double)?, gain: Float, wet wetURL: URL? = nil, done: @escaping (URL?, String?) -> Void) {
        // (the room's sound, made by Studio, whole in memory: added to the original as it goes)
        var wet: [[Float]] = [], wetRate: Double = 0
        if let wu = wetURL, let f = try? AVAudioFile(forReading: wu), let buf = AVAudioPCMBuffer(pcmFormat: f.processingFormat, frameCapacity: AVAudioFrameCount(f.length)) {
            if (try? f.read(into: buf)) != nil, let ch = buf.floatChannelData {
                let n = Int(buf.frameLength)
                for c in 0..<Int(buf.format.channelCount) { wet.append(Array(UnsafeBufferPointer(start: ch[c], count: n))) }
                wetRate = buf.format.sampleRate
            }
        }
        var wetPos = 0
        let out = FileManager.default.temporaryDirectory.appendingPathComponent("studio-final-" + UUID().uuidString + ".mp4")
        let filmAsset = AVURLAsset(url: film), soundAsset = AVURLAsset(url: sound)
        guard let vTrack = filmAsset.tracks(withMediaType: .video).first else { done(nil, "no pictures"); return }
        guard let aTrack = soundAsset.tracks(withMediaType: .audio).first else { done(film, nil); return }
        do {
            let vReader = try AVAssetReader(asset: filmAsset)
            let vOut = AVAssetReaderTrackOutput(track: vTrack, outputSettings: nil)   // (as it is)
            vReader.add(vOut)
            let aReader = try AVAssetReader(asset: soundAsset)
            if let r = range, r.1 > r.0 {
                aReader.timeRange = CMTimeRange(start: CMTime(seconds: r.0, preferredTimescale: 48000), end: CMTime(seconds: r.1, preferredTimescale: 48000))
            }
            let desc = aTrack.formatDescriptions.first.map { $0 as! CMAudioFormatDescription }
            let asbd = desc.flatMap { CMAudioFormatDescriptionGetStreamBasicDescription($0)?.pointee }
            let channels = max(1, min(2, Int(asbd?.mChannelsPerFrame ?? 2)))
            let rate = wetRate > 0 ? wetRate : (asbd?.mSampleRate ?? 48000) >= 44100 ? (asbd?.mSampleRate ?? 48000) : 48000
            let aOut = AVAssetReaderTrackOutput(track: aTrack, outputSettings: [
                AVFormatIDKey: kAudioFormatLinearPCM, AVLinearPCMBitDepthKey: 32, AVLinearPCMIsFloatKey: true,
                AVLinearPCMIsBigEndianKey: false, AVLinearPCMIsNonInterleaved: false,
                AVSampleRateKey: rate, AVNumberOfChannelsKey: channels,
            ])
            aReader.add(aOut)
            let writer = try AVAssetWriter(outputURL: out, fileType: .mp4)
            let vIn = AVAssetWriterInput(mediaType: .video, outputSettings: nil, sourceFormatHint: vTrack.formatDescriptions.first.map { $0 as! CMFormatDescription })
            vIn.expectsMediaDataInRealTime = false
            let aIn = AVAssetWriterInput(mediaType: .audio, outputSettings: [
                AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: rate, AVNumberOfChannelsKey: channels,
                AVEncoderBitRateKey: channels == 1 ? 192_000 : 256_000,
            ])
            aIn.expectsMediaDataInRealTime = false
            guard writer.canAdd(vIn), writer.canAdd(aIn) else { done(nil, "inputs"); return }
            writer.add(vIn); writer.add(aIn)
            guard vReader.startReading(), aReader.startReading(), writer.startWriting() else {
                done(nil, (writer.error ?? vReader.error ?? aReader.error)?.localizedDescription ?? "start"); return
            }
            writer.startSession(atSourceTime: .zero)
            let group = DispatchGroup()
            let filmEnd = filmAsset.duration
            group.enter()
            vIn.requestMediaDataWhenReady(on: DispatchQueue(label: "stand.mux.v")) {
                while vIn.isReadyForMoreMediaData {
                    guard let s = vOut.copyNextSampleBuffer() else { vIn.markAsFinished(); group.leave(); return }
                    if !vIn.append(s) { vReader.cancelReading(); vIn.markAsFinished(); group.leave(); return }
                }
            }
            group.enter()
            let start = range.map { CMTime(seconds: $0.0, preferredTimescale: 48000) } ?? .zero
            aIn.requestMediaDataWhenReady(on: DispatchQueue(label: "stand.mux.a")) {
                while aIn.isReadyForMoreMediaData {
                    guard let s = aOut.copyNextSampleBuffer() else { aIn.markAsFinished(); group.leave(); return }
                    // (from the start of the part used; nothing after the end of the pictures)
                    let pts = CMTimeSubtract(CMSampleBufferGetPresentationTimeStamp(s), start)
                    if CMTimeCompare(pts, filmEnd) >= 0 { aReader.cancelReading(); aIn.markAsFinished(); group.leave(); return }
                    if !wet.isEmpty { StandVideoKit.mix(s, gain: gain, channels: channels, wet: wet, pos: &wetPos) }
                    else if gain != 1 { StandVideoKit.scale(s, by: gain) }
                    var timing = CMSampleTimingInfo(duration: CMSampleBufferGetDuration(s), presentationTimeStamp: pts, decodeTimeStamp: .invalid)
                    var moved: CMSampleBuffer?
                    CMSampleBufferCreateCopyWithNewTiming(allocator: nil, sampleBuffer: s, sampleTimingEntryCount: 1, sampleTimingArray: &timing, sampleBufferOut: &moved)
                    if let m = moved, CMTimeCompare(pts, .zero) >= 0, !aIn.append(m) { aReader.cancelReading(); aIn.markAsFinished(); group.leave(); return }
                }
            }
            group.notify(queue: queue) {
                writer.finishWriting {
                    if writer.status == .completed { try? FileManager.default.removeItem(at: film); done(out, nil) }
                    else { try? FileManager.default.removeItem(at: out); done(nil, writer.error?.localizedDescription ?? "mux") }
                }
            }
        } catch { done(nil, error.localizedDescription) }
    }

    // the original, louder by `gain`, with the room's sound added (float samples, in place)
    private static func mix(_ s: CMSampleBuffer, gain: Float, channels: Int, wet: [[Float]], pos: inout Int) {
        guard let block = CMSampleBufferGetDataBuffer(s) else { return }
        var length = 0, total = 0; var ptr: UnsafeMutablePointer<Int8>?
        guard CMBlockBufferGetDataPointer(block, atOffset: 0, lengthAtOffsetOut: &length, totalLengthOut: &total, dataPointerOut: &ptr) == kCMBlockBufferNoErr, let p = ptr else { return }
        let n = length / MemoryLayout<Float>.size, frames = n / max(1, channels)
        let wn = wet[0].count, wc = wet.count
        let start = pos
        p.withMemoryRebound(to: Float.self, capacity: n) { f in
            for i in 0..<frames {
                let j = start + i
                for c in 0..<channels {
                    var w: Float = 0
                    if j < wn { w = channels == 1 && wc > 1 ? (wet[0][j] + wet[1][j]) * 0.5 : wet[min(c, wc - 1)][j] }
                    let k = i * channels + c
                    f[k] = max(-1, min(1, f[k] * gain + w))
                }
            }
        }
        pos += frames
    }

    // louder by `gain`, in place (float samples), never past full scale
    private static func scale(_ s: CMSampleBuffer, by gain: Float) {
        guard let block = CMSampleBufferGetDataBuffer(s) else { return }
        var length = 0, total = 0; var ptr: UnsafeMutablePointer<Int8>?
        guard CMBlockBufferGetDataPointer(block, atOffset: 0, lengthAtOffsetOut: &length, totalLengthOut: &total, dataPointerOut: &ptr) == kCMBlockBufferNoErr, let p = ptr else { return }
        let n = length / MemoryLayout<Float>.size
        p.withMemoryRebound(to: Float.self, capacity: n) { f in
            for k in 0..<n { f[k] = max(-1, min(1, f[k] * gain)) }
        }
    }

    private func outEvent(_ id: String, _ msg: [String: Any]) {
        var m = msg; m["id"] = id
        DispatchQueue.main.async { self.send?("standVideoOutEvent", m) }
    }
}
