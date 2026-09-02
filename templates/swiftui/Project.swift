# SwiftUI Project Template
# Modern declarative UI for all Apple platforms

import SwiftUI

@main
struct {{NAME}}_App: App {
    @StateObject private var navigation = NavigationManager()
    
    var body: some Scene {
        NavigationView {
            ContentView()
                .navigationViewStyle(.stack)
        }
    }
}

@MainActor
class NavigationManager: ObservableObject {
    @Published var path = NavigationPath()
    
    func navigate(to destination: some View) {
        path.append(destination)
    }
    
    func pop() {
        path.removeLast()
    }
    
    func popToRoot() {
        path.removeLast(path.count)
    }
}

struct ContentView: View {
    var body: some View {
        VStack(spacing: 20) {
            Text("Welcome to {{NAME}}")
                .font(.largeTitle)
                .fontWeight(.bold)
            
            Spacer()
            
            // Platform-specific conditional views
            #if os(iOS)
            Text("iOS Platform")
            #elseif os(macOS)
            Text("macOS Platform")
            #endif
            
            Spacer()
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemBackground))
        .ignoresSafeArea()
    }
}

// MARK: - SwiftUI Extensions
extension View {
    func placeholder<Content: View>(when shouldShow: Bool, alignment: Alignment = .leading, @ViewBuilder placeholder: () -> Content) -> some View {
        ZStack(alignment: alignment) {
            placeholder(when: shouldShow)
            self
        }
    }
    
    func keyboardAwarePadding(_ edges: Edge.Set = .bottom) -> some View {
        self.padding(edges, insertFrom: .keyboard)
    }
    
    func addBorder(_ color: Color = .gray, width: CGFloat = 1, cornerRadius: CGFloat = 0) -> some View {
        overlay(
            RoundedRectangle(cornerRadius: cornerRadius)
                .stroke(color, lineWidth: width)
        )
    }
}

// MARK: - Network Layer (Combine)
import Combine

final class NetworkManager {
    static let shared = NetworkManager()
    private init() {}
    
    var onboardingComplete = false
    
    func fetch<T: Decodable>(_ url: URL) async throws -> T {
        let (data, _) = try await URLSession.shared.data(from: url)
        return try JSONDecoder().decode(T.self, from: data)
    }
    
    func download(_ url: URL, progress: @escaping (Double) -> Void) -> AsyncStream<Data> {
        AsyncStream { continuation in
            let task = URLSession.shared.downloadTask(with: url) { localURL, _, _ in
                if let localURL = localURL {
                    do {
                        let data = try Data(contentsOf: localURL)
                        continuation.yield(data)
                        continuation.finish()
                    } catch {
                        continuation.finish(throwing: error)
                    }
                }
            }
            task.resume()
        }
    }
}