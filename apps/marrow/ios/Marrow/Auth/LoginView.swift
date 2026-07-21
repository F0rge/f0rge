import SwiftUI

struct LoginView: View {
    let onLogin: () -> Void

    @State private var email = ""
    @State private var password = ""
    @State private var errorMessage: String?
    @State private var busy = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Email", text: $email)
                        .keyboardType(.emailAddress)
                        .textContentType(.username)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField("Password", text: $password)
                        .textContentType(.password)
                }
                if let errorMessage {
                    Section {
                        Text(errorMessage).foregroundStyle(.red)
                    }
                }
                Section {
                    Button(busy ? "Signing in…" : "Sign in") {
                        Task { await login() }
                    }
                    .disabled(busy || email.isEmpty || password.isEmpty)
                }
            }
            .navigationTitle("Marrow")
        }
    }

    private func login() async {
        busy = true
        defer { busy = false }
        errorMessage = nil
        do {
            let output = try await API.client.loginApiV1AuthLoginPost(
                body: .json(.init(email: email, password: password))
            )
            switch output {
            case .ok(let ok):
                let status = try ok.body.json
                guard let token = status.token else {
                    errorMessage = "Login succeeded but the server returned no token."
                    return
                }
                Keychain.save(token)
                onLogin()
            case .unprocessableContent:
                errorMessage = "Invalid email or password format."
            case .undocumented(let statusCode, let payload):
                errorMessage = await API.errorDetail(from: payload) ?? "Login failed (HTTP \(statusCode))."
            }
        } catch {
            errorMessage = "Network error: \(error.localizedDescription)"
        }
    }
}
