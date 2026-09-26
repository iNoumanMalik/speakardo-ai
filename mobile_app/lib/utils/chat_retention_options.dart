/// How long chat history is kept on the server (must match backend
/// `models.CHAT_RETENTION_CHOICES`). `null` days = keep forever.
class ChatRetentionOption {
  const ChatRetentionOption({required this.days, required this.label});

  final int? days;
  final String label;
}

const int kDefaultChatRetentionDays = 90;

const List<ChatRetentionOption> kChatRetentionOptions = [
  ChatRetentionOption(days: 30, label: '30 days'),
  ChatRetentionOption(days: 90, label: '90 days'),
  ChatRetentionOption(days: 365, label: '1 year'),
  ChatRetentionOption(days: null, label: 'Forever'),
];

/// Settings subtitle, e.g. "Kept for 90 days" or "Kept forever".
String chatRetentionLabel(int? days) {
  if (days == null) return 'Kept forever';
  for (final option in kChatRetentionOptions) {
    if (option.days == days) return 'Kept for ${option.label}';
  }
  return 'Kept for $days days';
}
