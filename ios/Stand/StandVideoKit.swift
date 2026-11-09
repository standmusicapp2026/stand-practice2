import UIKit
import AVFoundation
import PhotosUI
import UniformTypeIdentifiers

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
// App → page:
//   standVideoInEvent({ type: "busy" | "done" | "error" | "cancel", video, audio, name, dur, w, h, fps, message })
//   standVideoOutEvent({ id, type: "ready" | "ack" | "src" | "progress" | "done" | "error", i, fps, w, h, hasAudio, path, f, message })

final class StandVideoKit: NSObject, PHPickerViewControllerDelegate, UIDocumentPickerDelegate {
    static let shared = StandVideoKit()
    var send: ((String, [String: Any]) -> Void)?

    // MARK: in

    func pick(from: String, on host: UIViewController) {
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
        init(id: String, w: Int, h: Int, fps: Int, rate: Int, url: URL) {
            self.id = id; self.w = w; self.h = h; self.fps = fps; self.rate = rate; self.url = url
        }
    }
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
                var waited = 0
                while !input.isReadyForMoreMediaData && waited < 1000 { usleep(5000); waited += 1 }
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
                let sound: URL? = audio == "src" ? job.src?.1 : audio == "wav" ? job.wav?.1 : nil
                if let sound = sound {
                    self.outEvent(id, ["type": "progress", "f": 0.97])
                    self.addSound(to: job.url, from: sound, range: audio == "src" ? (a, b) : nil, gain: audio == "src" ? gain : 1) { final, err in
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
        case "cancel":
            if let job = jobs.removeValue(forKey: id) { job.writer?.cancelWriting(); clean(job) }
        default: break
        }
    }

    private func startWriter(_ job: Job) -> String? {
        let w = job.w, h = job.h, fps = job.fps
        // (about 0.25 bit for each point of each picture: 1080×1920 at 30 a second ≈ 16 Mbit/s)
        let rate = job.rate > 0 ? job.rate : Int(Double(w * h * fps) * 0.25)
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
    private func addSound(to film: URL, from sound: URL, range: (Double, Double)?, gain: Float, done: @escaping (URL?, String?) -> Void) {
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
            let rate = (asbd?.mSampleRate ?? 48000) >= 44100 ? (asbd?.mSampleRate ?? 48000) : 48000
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
                    if gain != 1 { StandVideoKit.scale(s, by: gain) }
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
