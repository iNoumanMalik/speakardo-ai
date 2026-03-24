class Message {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final Map<String, dynamic>? pendingReminder;

  Message({
    required this.text,
    required this.isUser,
    required this.timestamp,
    this.pendingReminder,
  });

  Message copyWith({
    String? text,
    bool? isUser,
    DateTime? timestamp,
    Map<String, dynamic>? pendingReminder,
    bool clearPendingReminder = false,
  }) {
    return Message(
      text: text ?? this.text,
      isUser: isUser ?? this.isUser,
      timestamp: timestamp ?? this.timestamp,
      pendingReminder:
          clearPendingReminder ? null : (pendingReminder ?? this.pendingReminder),
    );
  }
}

