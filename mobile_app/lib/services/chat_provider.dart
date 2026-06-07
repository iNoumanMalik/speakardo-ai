import 'package:flutter/material.dart';
import '../models/message.dart';
import 'api_service.dart';
import 'package:intl/intl.dart';
// import 'tts_service.dart';
import '../utils/repeat_options.dart';

class ChatProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  final List<Message> _messages = [];
  bool _isLoading = false;

  /// Last assistant draft for Phase 2 (clarification, time follow-up, edit-in-chat).
  Map<String, dynamic>? _pendingContext;
  // bool _voiceFeedbackEnabled = true;

  List<Message> get messages => _messages;
  bool get isLoading => _isLoading;
  // bool get voiceFeedbackEnabled => _voiceFeedbackEnabled;

  // void setVoiceFeedbackEnabled(bool enabled) {
  //   _voiceFeedbackEnabled = enabled;
  //   if (!enabled) {
  //     TtsService.stop();
  //   }
  //   notifyListeners();
  // }

  void addMessage(Message message) {
    _messages.insert(0, message);
    notifyListeners();
  }

  void _addAssistantMessage(String displayText) {
    addMessage(
      Message(
        text: displayText,
        isUser: false,
        timestamp: DateTime.now(),
      ),
    );
    // TTS disabled — was: speak [ttsPhrase] for reminder confirmations / prompts.
    // if (ttsPhrase != null &&
    //     ttsPhrase.trim().isNotEmpty &&
    //     _voiceFeedbackEnabled) {
    //   TtsService.speak(ttsPhrase.trim());
    // }
  }

  // TTS disabled — short spoken lines for reminder draft replies.
  // String _shortTtsForDraftReply(
  //   String reply,
  //   Map<String, dynamic> draft,
  // ) {
  //   final confirmable = draft['confirmable'];
  //   if (confirmable == true) {
  //     if (draft['edit_reminder_id'] != null) {
  //       return 'Should I update this reminder? Tap yes or no.';
  //     }
  //     return 'Should I save this reminder? Tap yes or no.';
  //   }
  //   final time = draft['time'];
  //   final hasTime = time != null && time.toString().trim().isNotEmpty;
  //   if (!hasTime) {
  //     return 'What time should I remind you?';
  //   }
  //   if (reply.toLowerCase().contains('couldn\'t match') ||
  //       reply.toLowerCase().contains("couldn't match")) {
  //     return 'I could not match that to a saved reminder.';
  //   }
  //   return 'One quick question.';
  // }

  void _clearPendingReminderFor(Map<String, dynamic> reminderData) {
    final int idx = _messages.indexWhere(
      (m) =>
          !m.isUser &&
          m.pendingReminder != null &&
          identical(m.pendingReminder, reminderData),
    );
    if (idx != -1) {
      _messages[idx] = _messages[idx].copyWith(clearPendingReminder: true);
    }
  }

  Future<void> sendMessage(String text) async {
    addMessage(Message(
      text: text,
      isUser: true,
      timestamp: DateTime.now(),
    ));

    _isLoading = true;
    notifyListeners();

    try {
      final response = await _apiService.sendMessage(
        text,
        pendingContext: _pendingContext,
      );

      final reply = response['reply'] as String? ?? '';
      final parsedReminder = response['parsed_reminder'];

      if (parsedReminder is Map) {
        final draft = Map<String, dynamic>.from(parsedReminder);
        _pendingContext = draft;
        addMessage(Message(
          text: reply,
          isUser: false,
          timestamp: DateTime.now(),
          pendingReminder: draft,
        ));
        // TTS disabled — was: TtsService.speak(_shortTtsForDraftReply(...))
      } else {
        _pendingContext = null;
        _addAssistantMessage(reply);
        // TTS disabled — was: spoken greeting / error lines for hello & parse failures.
      }
    } catch (e) {
      _addAssistantMessage('Error: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> confirmReminder(Map<String, dynamic> reminderData) async {
    if (reminderData['confirmable'] == false) {
      return false;
    }

    _isLoading = true;
    notifyListeners();

    try {
      final String task = reminderData['task'] ?? 'No Task';
      final String date =
          reminderData['date'] ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
      final String time = reminderData['time'] ?? '00:00';
      final String? repeat = reminderData['repeat'] as String?;
      final editId = reminderData['edit_reminder_id']?.toString();

      final normalizedTime = time.length == 5 ? '$time:00' : time;
      final DateTime local = DateTime.parse('${date}T$normalizedTime');

      final repeatLabel = repeatDisplayLabel(repeat);
      final repeatNote =
          repeatLabel != null ? ' Repeats $repeatLabel.' : '';

      if (editId != null && editId.isNotEmpty) {
        await _apiService.patchReminder(editId, {
          'task': task,
          'datetime': local.toUtc().toIso8601String(),
          'repeat': normalizeRepeatValue(repeat),
        });
        _clearPendingReminderFor(reminderData);
        _pendingContext = null;
        _addAssistantMessage(
          'Reminder updated: "$task" on $date at $time.$repeatNote',
        );
      } else {
        await _apiService.createReminder({
          'task': task,
          'datetime': local.toUtc().toIso8601String(),
          'repeat': normalizeRepeatValue(repeat),
        });
        _clearPendingReminderFor(reminderData);
        _pendingContext = null;
        _addAssistantMessage(
          "Reminder saved! I'll remind you to $task on $date at $time.$repeatNote",
        );
      }
      return true;
    } catch (e) {
      _addAssistantMessage(
        reminderData['edit_reminder_id'] != null
            ? 'Failed to update reminder: $e'
            : 'Failed to save reminder: $e',
      );
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void rejectReminder(Map<String, dynamic> reminderData) {
    _clearPendingReminderFor(reminderData);
    _pendingContext = null;
    _addAssistantMessage(
      'No problem. Please tell me the reminder again with updated details '
      '(for example: \'Remind me to take medicine at 12 PM\').',
    );
    notifyListeners();
  }
}
