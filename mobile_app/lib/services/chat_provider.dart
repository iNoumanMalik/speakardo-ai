import 'package:flutter/material.dart';
import '../models/message.dart';
import 'api_service.dart';
import 'package:intl/intl.dart';
import 'tts_service.dart';

class ChatProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  final List<Message> _messages = [];
  bool _isLoading = false;

  /// Last assistant draft for Phase 2 (clarification, time follow-up, edit-in-chat).
  Map<String, dynamic>? _pendingContext;
  bool _voiceFeedbackEnabled = true;

  List<Message> get messages => _messages;
  bool get isLoading => _isLoading;
  bool get voiceFeedbackEnabled => _voiceFeedbackEnabled;

  void setVoiceFeedbackEnabled(bool enabled) {
    _voiceFeedbackEnabled = enabled;
    if (!enabled) {
      TtsService.stop();
    }
    notifyListeners();
  }

  void addMessage(Message message) {
    _messages.insert(0, message);
    notifyListeners();
  }

  /// [displayText] is shown in chat; [ttsPhrase] is spoken when non-null (short polish).
  void _addAssistantMessage(
    String displayText, {
    String? ttsPhrase,
  }) {
    addMessage(
      Message(
        text: displayText,
        isUser: false,
        timestamp: DateTime.now(),
      ),
    );
    if (ttsPhrase != null &&
        ttsPhrase.trim().isNotEmpty &&
        _voiceFeedbackEnabled) {
      TtsService.speak(ttsPhrase.trim());
    }
  }

  /// Short voice line for assistant replies that also carry a reminder draft.
  String _shortTtsForDraftReply(
    String reply,
    Map<String, dynamic> draft,
  ) {
    final confirmable = draft['confirmable'];
    if (confirmable == true) {
      return 'Should I save this reminder? Tap yes or no.';
    }
    final time = draft['time'];
    final hasTime = time != null && time.toString().trim().isNotEmpty;
    if (!hasTime) {
      return 'What time should I remind you?';
    }
    if (reply.toLowerCase().contains('couldn\'t match') ||
        reply.toLowerCase().contains("couldn't match")) {
      return 'I could not match that to a saved reminder.';
    }
    return 'One quick question.';
  }

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

  DateTime _localDateTimeFromDraft(Map<String, dynamic> action) {
    final String date = action['date'] as String;
    final String time = action['time'] as String;
    final normalizedTime = time.length == 5 ? '$time:00' : time;
    return DateTime.parse('${date}T$normalizedTime');
  }

  Future<void> _applyClientAction(Map<String, dynamic> action) async {
    final type = action['type']?.toString();
    if (type != 'patch_reminder') return;

    final id = action['reminder_id']?.toString();
    if (id == null || id.isEmpty) return;

    final task = action['task'] as String?;
    if (task == null) return;

    final local = _localDateTimeFromDraft({
      'date': action['date'],
      'time': action['time'],
    });

    final payload = <String, dynamic>{
      'task': task,
      'datetime': local.toUtc().toIso8601String(),
    };
    final repeat = action['repeat'];
    if (repeat != null) {
      payload['repeat'] = repeat;
    }

    await _apiService.patchReminder(id, payload);
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
      final clientAction = response['client_action'];
      final parsedReminder = response['parsed_reminder'];

      if (clientAction is Map) {
        try {
          await _applyClientAction(Map<String, dynamic>.from(clientAction));
          _pendingContext = null;
          _addAssistantMessage(
            reply,
            ttsPhrase: 'Reminder updated.',
          );
        } catch (e) {
          _addAssistantMessage('Could not update reminder: $e');
        }
        return;
      }

      if (parsedReminder is Map) {
        final draft = Map<String, dynamic>.from(parsedReminder);
        _pendingContext = draft;
        addMessage(Message(
          text: reply,
          isUser: false,
          timestamp: DateTime.now(),
          pendingReminder: draft,
        ));
        if (_voiceFeedbackEnabled) {
          final phrase = _shortTtsForDraftReply(reply, draft);
          if (phrase.isNotEmpty) {
            TtsService.speak(phrase);
          }
        }
      } else {
        _pendingContext = null;
        final lower = reply.toLowerCase();
        String? tts;
        if (lower.contains('hello!') || lower.contains("i'm your ai")) {
          tts = 'Hi! What reminder can I set?';
        } else if (lower.contains("couldn't quite understand") ||
            lower.contains('could not quite understand')) {
          tts = 'Sorry, I did not catch that. Try again.';
        }
        _addAssistantMessage(reply, ttsPhrase: tts);
      }
    } catch (e) {
      _addAssistantMessage('Error: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> confirmReminder(Map<String, dynamic> reminderData) async {
    if (reminderData['confirmable'] == false) {
      return;
    }

    _isLoading = true;
    notifyListeners();

    try {
      final String task = reminderData['task'] ?? 'No Task';
      final String date =
          reminderData['date'] ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
      final String time = reminderData['time'] ?? '00:00';
      final String? repeat = reminderData['repeat'] as String?;

      final normalizedTime = time.length == 5 ? '$time:00' : time;
      final DateTime local = DateTime.parse('${date}T$normalizedTime');

      await _apiService.createReminder({
        'task': task,
        'datetime': local.toUtc().toIso8601String(),
        'repeat': repeat,
      });

      _clearPendingReminderFor(reminderData);
      _pendingContext = null;

      _addAssistantMessage(
        "Reminder saved! I'll remind you to $task on $date at $time.",
        ttsPhrase: 'Reminder saved.',
      );
    } catch (e) {
      _addAssistantMessage('Failed to save reminder: $e');
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
      ttsPhrase: 'Okay. Tell me the reminder again when you are ready.',
    );
    notifyListeners();
  }
}
