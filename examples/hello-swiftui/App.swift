# SwiftUI App Template
# Complete app with all Apple frameworks integration

import SwiftUI
import Combine
import CoreData
import CoreLocation
import UIKit

@main
struct {{NAME}}_App: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var navigation = NavigationManager()
    @State private var isOnboarding = true
    
    var body: some Scene {
        WindowGroup {
            if isOnboarding {
                OnboardingView(isOnboarding: $isOnboarding)
            } else {
                MainTabView()
                    .environment(\.managedObjectContext, CoreDataProvider.shared.context)
            }
        }
    }
}

// MARK: - App Delegate
class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        // Setup Core Data
        CoreDataManager.shared.setup()
        
        // Request permissions
        LocationManager.shared.requestPermissions()
        
        // Configure notifications
        NotificationManager.shared.requestAuthorization()
        
        // App Tracking Transparency
        if #available(iOS 14, *) {
            ATTrackingManager.requestTrackingAuthorization { status in
                // Handle ATT completion
            }
        }
        
        return true
    }
    
    func application(_ application: UIApplication, configurationForConnecting scene: UIScene, options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        UISceneConfiguration(name: nil, sessionRole: scene.session.role)
    }
    
    func application(_ application: UIApplication, didDiscardSceneSessions sceneSessions: Set<UISceneSession>) {
        // Handle discarded scenes
    }
}

// MARK: - Core Data Stack
struct CoreDataManager {
    static let shared = CoreDataManager()
    let persistentContainer: NSPersistentContainer = {
        let container = NSPersistentContainer(name: "{{NAME}}")
        container.loadPersistentStores(completion: { (storeDescription, error) in
            if let error = error as NSError? {
                fatalError("Unresolved error \(error), \(error.userInfo)")
            }
        })
        return container
    }()
    
    static var context: NSManagedObjectContext {
        return shared.persistentContainer.viewContext
    }
}

// MARK: - Location Manager
class LocationManager: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    
    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }
    
    func requestPermissions() {
        if CLLocationManager.authorizationStatus() == .notDetermined {
            manager.requestWhenInUseAuthorization()
        }
    }
    
    func getCurrentLocation() -> CLLocation? {
        return manager.location
    }
}

// MARK: - Notification Manager
class NotificationManager {
    static let shared = NotificationManager()
    private init() {}
    
    func requestAuthorization() {
        UNUserNotificationCenter.current()
            .requestAuthorization(options: [.alert, .badge, .sound]) { granted, _ in
                // Handle authorization
            }
    }
    
    func scheduleNotification(title: String, body: String, delay: TimeInterval) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: delay, repeats: false)
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: trigger)
        
        UNUserNotificationCenter.current().add(request)
    }
}

// MARK: - Navigation
@MainActor
class NavigationManager: ObservableObject {
    @Published var path = NavigationPath()
    
    func navigate<T: View>(to destination: T) {
        path.append(destination)
    }
    
    func pop() {
        guard !path.isEmpty else { return }
        path.removeLast()
    }
    
    func popToRoot() {
        path.removeLast(path.count)
    }
}

// MARK: - Views
struct MainTabView: View {
    @StateObject private var navigation = NavigationManager()
    
    var body: some View {
        TabView {
            HomeView()
                .tabItem {
                    Label("Home", systemImage: "house")
                }
            SearchView()
                .tabItem {
                    Label("Search", systemImage: "magnifyingglass")
                }
            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
        }
        .environmentObject(navigation)
    }
}

struct HomeView: View {
    @StateObject private var network = NetworkManager.shared
    
    var body: some View {
        VStack {
            Text("Welcome!")
            if let user = network.user {
                Text("Hello, \(user.name)")
            }
            Button("Refresh") {
                network.fetchCurrentUser()
            }
        }
        .padding()
    }
}

struct SearchView: View {
    var body: some View {
        VStack {
            Text("Search functionality")
        }
    }
}

struct SettingsView: View {
    var body: some View {
        VStack {
            Text("Settings")
        }
    }
}

// MARK: - Network Manager
final class NetworkManager {
    static let shared = NetworkManager()
    private init() {}
    
    @Published var user: User?
    
    func fetchCurrentUser() {
        Task {
            do {
                // Replace with actual API call
                let user = try await UserService.fetch()
                self.user = user
            } catch {
                print("Failed to fetch user: \(error)")
            }
        }
    }
    
    func logout() {
        self.user = nil
    }
}

// MARK: - Models
struct User: Decodable {
    let id: String
    let name: String
    let email: String
}

// MARK: - Preview
struct {{NAME}}_App_Previews: PreviewProvider {
    static var previews: some View {
        HomeView()
    }
}