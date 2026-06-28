import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/message.dart';
import '../services/chat_provider.dart';
import '../services/reminder_provider.dart';
import '../utils/repeat_options.dart';
import 'app_chrome.dart';

class MessageBubble extends StatelessWidget {
  final Message message;

  const MessageBubble({
    super.key,
    required this.message,
  });

  @override
  Widget build(BuildContext context) {
    bool isUser = message.isUser;
    final pending = message.pendingReminder;
    final bool showConfirm = pending != null && pending['confirmable'] != false;
    final bool isEdit = pending?['edit_reminder_id'] != null;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 16.0),
      child: Column(
        crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          Align(
            alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                if (!isUser) ...[
                  const AppLogoMark(size: 32),
                  const SizedBox(width: 8),
                ],
                Flexible(
                  child: Container(
                    constraints: BoxConstraints(
                      maxWidth: MediaQuery.sizeOf(context).width * 0.78,
                    ),
                    decoration: BoxDecoration(
                      color: isUser
                          ? AppChrome.primary
                          : Colors.white.withValues(alpha: 0.82),
                      border: Border.all(
                        color: isUser
                            ? AppChrome.primary
                            : Colors.white.withValues(alpha: 0.85),
                      ),
                      borderRadius: BorderRadius.only(
                        topLeft: const Radius.circular(24),
                        topRight: const Radius.circular(24),
                        bottomLeft:
                            isUser ? const Radius.circular(24) : const Radius.circular(5),
                        bottomRight:
                            isUser ? const Radius.circular(5) : const Radius.circular(24),
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.04),
                          blurRadius: 14,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 17,
                      vertical: 14,
                    ),
                    child: Text(
                      message.text,
                      style: TextStyle(
                        color: isUser ? Colors.white : AppChrome.ink,
                        fontSize: 15.5,
                        height: 1.35,
                        fontWeight: isUser ? FontWeight.w600 : FontWeight.w500,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (showConfirm) ...[
            if (_pendingSummary(pending) != null)
              Padding(
                padding: const EdgeInsets.only(top: 8, left: 42),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 9,
                  ),
                  decoration: BoxDecoration(
                    color: AppChrome.accent.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: AppChrome.accent.withValues(alpha: 0.15),
                    ),
                  ),
                  child: Text(
                    _pendingSummary(pending)!,
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppChrome.ink,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),
            Padding(
              padding: const EdgeInsets.only(top: 10.0, left: 42.0),
              child: Row(
                children: [
                  FilledButton.icon(
                    onPressed: () async {
                      final ok = await context
                          .read<ChatProvider>()
                          .confirmReminder(message.pendingReminder!);
                      if (ok && context.mounted) {
                        // Keep reminders list in sync after chat edit/create.
                        try {
                          // ignore: use_build_context_synchronously
                          await context.read<ReminderProvider>().fetchReminders();
                        } catch (_) {}
                      }
                    },
                    style: AppChrome.primaryButtonStyle(),
                    icon: const Icon(Icons.check_circle_rounded, size: 18),
                    label: Text(isEdit ? 'Yes, update' : 'Yes, remind me'),
                  ),
                  const SizedBox(width: 8),
                  TextButton(
                    onPressed: () {
                      context.read<ChatProvider>().rejectReminder(message.pendingReminder!);
                    },
                    child: const Text("No"),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  String? _pendingSummary(Map<String, dynamic>? draft) {
    if (draft == null) return null;
    final task = draft['task']?.toString();
    final date = draft['date']?.toString();
    final time = draft['time']?.toString();
    if (task == null || date == null || time == null) return null;
    final repeat = repeatDisplayLabel(draft['repeat']?.toString());
    final repeatPart = repeat != null ? ' · $repeat' : ' · One time';
    return '$task — $date $time$repeatPart';
  }
}
