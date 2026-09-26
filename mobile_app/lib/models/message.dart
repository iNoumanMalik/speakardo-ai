class Message {
  /// Server id from /chat/history; null for messages created in this session.
  final String? id;
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final Map<String, dynamic>? pendingReminder;

  Message({
    this.id,
    required this.text,
    required this.isUser,
    required this.timestamp,
    this.pendingReminder,
  });

  /// A stored message from GET /chat/history. Restored messages never carry a
  /// reminder draft, so old Yes/No buttons cannot reappear.
  factory Message.fromHistoryJson(Map<String, dynamic> json) {
    return Message(
      id: json['id']?.toString(),
      text: json['content'] as String? ?? '',
      isUser: json['role'] == 'user',
      timestamp: DateTime.parse(json['created_at'] as String).toLocal(),
    );
  }

  Message copyWith({
    String? text,
    bool? isUser,
    DateTime? timestamp,
    Map<String, dynamic>? pendingReminder,
    bool clearPendingReminder = false,
  }) {
    return Message(
      id: id,
      text: text ?? this.text,
      isUser: isUser ?? this.isUser,
      timestamp: timestamp ?? this.timestamp,
      pendingReminder:
          clearPendingReminder ? null : (pendingReminder ?? this.pendingReminder),
    );
  }
}
