import SwiftUI

/// Teach the till a product it has never seen: five views, a name, a price.
/// No training happens; each view becomes one vector in the gallery.
struct EnrolView: View {
    @EnvironmentObject var store: Store
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var price = 20.0
    @State private var category = "chips"
    @State private var stock = 10
    @State private var restricted: Restriction = .none
    @State private var frames: [Frame] = []
    @State private var note = ""
    static let views = 5

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    CameraPreview()
                    Text("Put the product on the mat, then capture \(Self.views) views. Turn it a little between each one.")
                        .font(.footnote).foregroundStyle(.secondary)
                    Button {
                        capture()
                    } label: {
                        Text("CAPTURE VIEW \(min(frames.count + 1, Self.views)) OF \(Self.views)")
                    }
                    .buttonStyle(BigButtonStyle(fill: Theme.accent)).disabled(frames.count >= Self.views)
                    Text(progress).font(.footnote).foregroundStyle(.secondary)
                }
                Section("Product") {
                    TextField("Name", text: $name)
                    HStack { Text("Price"); Spacer(); TextField("Price", value: $price, format: .number).keyboardType(.decimalPad).multilineTextAlignment(.trailing) }
                    Picker("Category", selection: $category) { ForEach(["chips", "drinks", "sweets", "other"], id: \.self) { Text($0) } }
                    Stepper("Opening stock: \(stock)", value: $stock, in: 0...9999)
                    Picker("Restricted sale", selection: $restricted) {
                        Text("none").tag(Restriction.none)
                        Text("alcohol (11:00-24:00, ID check)").tag(Restriction.alcohol)
                        Text("tobacco (staff only)").tag(Restriction.tobacco)
                    }
                }
                if !note.isEmpty { Text(note).foregroundStyle(Theme.warn) }
            }
            .paperGround()
            .navigationTitle("Add a product")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save", action: save).disabled(frames.isEmpty || name.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
    }

    private var progress: String {
        "\(frames.count) of \(Self.views) views captured" + (frames.count < Self.views ? " - turn the product and capture again" : " - ready to save")
    }

    private func capture() {
        guard let frame = store.camera.latest() else { note = "No camera frame - check the camera."; return }
        guard !store.pipeline.proposer.propose(frame).isEmpty else { note = "Nothing on the mat - place the product and try again."; return }
        note = ""
        frames.append(frame)
    }

    private func save() {
        do {
            try store.enrol(name: name.trimmingCharacters(in: .whitespaces), price: price, category: category,
                            stock: stock, restricted: restricted, frames: frames)
            dismiss()
        } catch {
            note = error.localizedDescription
        }
    }
}
