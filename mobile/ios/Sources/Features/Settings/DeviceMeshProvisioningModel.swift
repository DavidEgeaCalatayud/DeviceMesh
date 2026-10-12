import Foundation
import ESPProvision

@MainActor
final class DeviceMeshProvisioningModel: NSObject, ObservableObject, ESPDeviceConnectionDelegate {
    @Published var devices: [ESPDevice] = []
    @Published var status = ""
    @Published var busy = false

    private var proofOfPossession = ""

    func scan() {
        status = "Scanning for DeviceMesh hardware…"
        devices = []
        ESPProvisionManager.shared.searchESPDevices(
            devicePrefix: "DM-",
            transport: .ble,
            security: .secure
        ) { [weak self] devices, error in
            Task { @MainActor in
                guard let self else { return }
                if let devices {
                    self.devices = devices
                    self.status = devices.isEmpty ? "No DM-* devices found" : "Select a device"
                } else {
                    self.status = error.map { String(describing: $0) } ?? "BLE scan failed"
                }
            }
        }
    }

    func provision(
        device: ESPDevice,
        proofOfPossession: String,
        serverURL: URL,
        enrollmentToken: String,
        ssid: String,
        passphrase: String
    ) async {
        busy = true
        status = "Establishing encrypted BLE session…"
        defer { busy = false }
        do {
            guard serverURL.scheme?.lowercased() == "https",
                  serverURL.host != nil else {
                throw ProvisioningError.invalidServer
            }
            guard proofOfPossession.count >= 8 else {
                throw ProvisioningError.invalidProof
            }
            guard !ssid.isEmpty else {
                throw ProvisioningError.missingSSID
            }
            self.proofOfPossession = proofOfPossession
            try await connect(device)
            status = "Sending DeviceMesh enrollment…"
            try await sendDeviceMeshConfiguration(
                device,
                serverURL: serverURL,
                enrollmentToken: enrollmentToken
            )
            status = "Provisioning Wi-Fi…"
            try await provisionWifi(device, ssid: ssid, passphrase: passphrase)
            status = "Provisioning complete. Device will enroll automatically."
            device.disconnect()
        } catch {
            status = error.localizedDescription
            device.disconnect()
        }
    }

    func getProofOfPossesion(
        forDevice: ESPDevice,
        completionHandler: @escaping (String) -> Void
    ) {
        completionHandler(proofOfPossession)
    }

    func getUsername(
        forDevice: ESPDevice,
        completionHandler: @escaping (String?) -> Void
    ) {
        completionHandler(nil)
    }

    private func connect(_ device: ESPDevice) async throws {
        try await withCheckedThrowingContinuation { continuation in
            device.connect(delegate: self) { sessionStatus in
                switch sessionStatus {
                case .connected:
                    continuation.resume()
                case let .failedToConnect(error):
                    continuation.resume(throwing: ProvisioningError.session(String(describing: error)))
                case .disconnected:
                    continuation.resume(throwing: ProvisioningError.disconnected)
                }
            }
        }
    }

    private func sendDeviceMeshConfiguration(
        _ device: ESPDevice,
        serverURL: URL,
        enrollmentToken: String
    ) async throws {
        let payload = try JSONSerialization.data(
            withJSONObject: [
                "serverUrl": serverURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/")),
                "enrollmentToken": enrollmentToken,
            ]
        )
        try await withCheckedThrowingContinuation { continuation in
            device.sendData(path: "devicemesh-config", data: payload) { response, error in
                if let error {
                    continuation.resume(throwing: ProvisioningError.session(String(describing: error)))
                    return
                }
                guard let response,
                      let object = try? JSONSerialization.jsonObject(with: response) as? [String: Any],
                      object["status"] as? String == "ok" else {
                    continuation.resume(throwing: ProvisioningError.configurationRejected)
                    return
                }
                continuation.resume()
            }
        }
    }

    private func provisionWifi(
        _ device: ESPDevice,
        ssid: String,
        passphrase: String
    ) async throws {
        try await withCheckedThrowingContinuation { continuation in
            var completed = false
            device.provision(ssid: ssid, passPhrase: passphrase) { status in
                guard !completed else { return }
                switch status {
                case .success:
                    completed = true
                    continuation.resume()
                case let .failure(error):
                    completed = true
                    continuation.resume(
                        throwing: ProvisioningError.wifi(String(describing: error))
                    )
                case .configApplied:
                    break
                }
            }
        }
    }

    enum ProvisioningError: LocalizedError {
        case invalidServer
        case invalidProof
        case missingSSID
        case session(String)
        case disconnected
        case configurationRejected
        case wifi(String)

        var errorDescription: String? {
            switch self {
            case .invalidServer: return "Hardware provisioning requires an HTTPS DeviceMesh server."
            case .invalidProof: return "Proof of possession is too short."
            case .missingSSID: return "Wi-Fi SSID is required."
            case let .session(message): return "BLE session failed: \(message)"
            case .disconnected: return "The ESP32 disconnected during provisioning."
            case .configurationRejected: return "The ESP32 rejected DeviceMesh configuration."
            case let .wifi(message): return "Wi-Fi provisioning failed: \(message)"
            }
        }
    }
}
