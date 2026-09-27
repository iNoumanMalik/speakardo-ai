/// A chip under an assistant reply: "Saved · Undo", "Forgot · Undo",
/// "Not saved: sensitive". Built from `memory_actions` in the /chat response.
class MemoryAction {
  const MemoryAction({
    required this.type,
    required this.label,
    this.memoryId,
    this.undo = false,
    this.undone = false,
  });

  /// saved | updated | forgotten | used | not_saved
  final String type;
  final String label;
  final String? memoryId;

  /// The server allows undoing this action.
  final bool undo;

  /// The user already tapped Undo.
  final bool undone;

  bool get canUndo => undo && !undone && memoryId != null;

  factory MemoryAction.fromJson(Map<String, dynamic> json) {
    return MemoryAction(
      type: json['type'] as String? ?? '',
      label: json['label'] as String? ?? '',
      memoryId: json['memory_id']?.toString(),
      undo: json['undo'] as bool? ?? false,
    );
  }

  MemoryAction markUndone() => MemoryAction(
        type: type,
        label: label,
        memoryId: memoryId,
        undo: undo,
        undone: true,
      );
}
