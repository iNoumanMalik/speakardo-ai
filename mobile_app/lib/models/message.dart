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
}

