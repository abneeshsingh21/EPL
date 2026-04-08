import SwiftUI

struct ContentView: View {
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    Text("EPL Auth Demo v1.0.0")
                    Text(greet("World"))
                    Text(make_greeting("Abneesh"))
                }
                .padding()
            }
            .navigationTitle("EPL Auth Demo")
        }
    }

    func greet(_ name: String) {
    }

    func make_greeting(_ username: String) {
    }
}

#Preview {
    ContentView()
}
