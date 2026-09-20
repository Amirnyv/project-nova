import AVFoundation
import Speech
import Combine

@MainActor
final class JarvisVoiceManager: NSObject, ObservableObject, AVSpeechSynthesizerDelegate {
    @Published private(set) var listening = false
    @Published private(set) var speaking = false
    @Published private(set) var requestingPermission = false
    @Published var errorMessage: String?
    var onTranscript: ((String) -> Void)?
    var onFinal: (() -> Void)?
    private let engine = AVAudioEngine()
    private let synthesizer = AVSpeechSynthesizer()
    private var recognition: SFSpeechRecognitionTask?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var hasTap = false
    private var generation = UUID()
    private var utteranceID: ObjectIdentifier?
    private var listeningTimeout: Task<Void, Never>?

    override init() {
        super.init()
        synthesizer.delegate = self
    }

    func start() async {
        guard !listening, !requestingPermission else { return }
        stop()
        errorMessage = nil
        requestingPermission = true
        let token = generation
        defer { requestingPermission = false }
        let speech = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0) }
        }
        guard token == generation else { return }
        guard speech == .authorized else {
            errorMessage = speech == .restricted
                ? "Speech recognition is restricted on this iPhone. Use a text command."
                : "Enable Speech Recognition for Nova in Settings to use voice."
            return
        }
        let microphone = await AVAudioApplication.requestRecordPermission()
        guard token == generation else { return }
        guard speech == .authorized, microphone else {
            errorMessage = "Enable Microphone and Speech Recognition for Nova in Settings to use voice. Text commands are still available."
            return
        }
        guard let recognizer = SFSpeechRecognizer(), recognizer.isAvailable else {
            errorMessage = "Speech recognition is unavailable. Please use a text command."
            return
        }
        do {
            let audio = AVAudioSession.sharedInstance()
            try audio.setCategory(.record, mode: .measurement, options: [])
            try audio.setActive(true)
            let bufferRequest = SFSpeechAudioBufferRecognitionRequest()
            bufferRequest.shouldReportPartialResults = true
            request = bufferRequest
            let input = engine.inputNode
            let format = input.outputFormat(forBus: 0)
            guard format.sampleRate > 0, format.channelCount > 0 else {
                throw JarvisFailure(message: "No microphone is available.")
            }
            input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
                bufferRequest.append(buffer)
            }
            hasTap = true
            listening = true
            recognition = recognizer.recognitionTask(with: bufferRequest) { [weak self] result, error in
                let text = result?.bestTranscription.formattedString
                let final = result?.isFinal == true
                let failed = error != nil
                Task { @MainActor [weak self] in
                    guard let self, self.generation == token, self.listening else { return }
                    if let text { self.onTranscript?(text) }
                    if final {
                        self.stopListening()
                        self.onFinal?()
                    } else if failed {
                        self.stopListening()
                        self.errorMessage = "Voice recognition stopped. Review the text and send it, or try again."
                    }
                }
            }
            engine.prepare()
            try engine.start()
            // Bound sessions even if the recognition service never sends a final callback.
            listeningTimeout = Task { [weak self] in
                do { try await Task.sleep(for: .seconds(60)) } catch { return }
                guard let self, self.generation == token, self.listening else { return }
                self.stopListening()
                self.errorMessage = "Listening timed out. Review the text and send it, or try again."
            }
        } catch {
            stopListening()
            errorMessage = error.localizedDescription
        }
    }

    func stopListening() {
        generation = UUID()
        listeningTimeout?.cancel()
        listeningTimeout = nil
        engine.stop()
        if hasTap { engine.inputNode.removeTap(onBus: 0); hasTap = false }
        request?.endAudio()
        recognition?.cancel()
        recognition = nil
        request = nil
        listening = false
        if !speaking {
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        }
    }

    func speak(_ text: String) {
        stop()
        guard !text.isEmpty else { return }
        do {
            let audio = AVAudioSession.sharedInstance()
            try audio.setCategory(.playback, mode: .spokenAudio, options: .duckOthers)
            try audio.setActive(true)
            speaking = true
            let utterance = AVSpeechUtterance(string: text)
            utteranceID = ObjectIdentifier(utterance)
            synthesizer.speak(utterance)
        } catch { errorMessage = error.localizedDescription }
    }

    func stop() {
        // Invalidate old callbacks before stopping; a late TTS callback must not
        // deactivate the audio session of a subsequent recognition request.
        utteranceID = nil
        synthesizer.stopSpeaking(at: .immediate)
        speaking = false
        stopListening()
    }

    private func finishSpeech(_ id: ObjectIdentifier) {
        guard utteranceID == id else { return }
        utteranceID = nil
        speaking = false
        if !listening {
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        }
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        let id = ObjectIdentifier(utterance)
        Task { @MainActor [weak self] in self?.finishSpeech(id) }
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        let id = ObjectIdentifier(utterance)
        Task { @MainActor [weak self] in self?.finishSpeech(id) }
    }
}
