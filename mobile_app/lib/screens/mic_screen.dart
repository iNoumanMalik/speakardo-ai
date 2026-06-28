import 'package:flutter/material.dart';

import '../widgets/app_chrome.dart';

class MicScreen extends StatelessWidget {
  const MicScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SpeakardoScaffold(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 112),
        children: const [
          SpeakardoTopBar(
            title: 'Voice Capture',
            subtitle: 'Fast reminder intake',
            leading: _MicBadge(),
          ),
          SizedBox(height: 30),
          _VoiceConsole(),
          SizedBox(height: 24),
          _QuickPrompts(),
          SizedBox(height: 24),
          _VoiceNotesPanel(),
        ],
      ),
    );
  }
}

class _MicBadge extends StatelessWidget {
  const _MicBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 46,
      height: 46,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: AppChrome.primary,
        border: Border.all(color: Colors.white, width: 3),
        boxShadow: [
          BoxShadow(
            color: AppChrome.primary.withValues(alpha: 0.3),
            blurRadius: 22,
            offset: const Offset(0, 9),
          ),
        ],
      ),
      child: const Icon(Icons.mic_rounded, color: Colors.white),
    );
  }
}

class _VoiceConsole extends StatelessWidget {
  const _VoiceConsole();

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      borderRadius: 32,
      padding: const EdgeInsets.fromLTRB(22, 30, 22, 22),
      child: Column(
        children: [
          SizedBox(
            height: 190,
            child: Stack(
              alignment: Alignment.center,
              children: [
                Container(
                  width: 170,
                  height: 170,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: AppChrome.primary.withValues(alpha: 0.12),
                    ),
                  ),
                ),
                Container(
                  width: 126,
                  height: 126,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppChrome.primary.withValues(alpha: 0.1),
                  ),
                ),
                Container(
                  width: 88,
                  height: 88,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppChrome.primary,
                  ),
                  child: const Icon(
                    Icons.mic_rounded,
                    color: Colors.white,
                    size: 38,
                  ),
                ),
                const Positioned(
                  bottom: 20,
                  child: _WaveBars(),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Tap to speak',
            style: TextStyle(
              color: AppChrome.ink,
              fontSize: 24,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'This screen is prepared for the dedicated voice flow. Current voice input still runs from Chat.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppChrome.muted, height: 1.4),
          ),
          const SizedBox(height: 22),
          FilledButton.icon(
            onPressed: null,
            style: AppChrome.primaryButtonStyle(),
            icon: const Icon(Icons.graphic_eq_rounded),
            label: const Text('Voice flow coming soon'),
          ),
        ],
      ),
    );
  }
}

class _WaveBars extends StatelessWidget {
  const _WaveBars();

  @override
  Widget build(BuildContext context) {
    const heights = [14.0, 24.0, 36.0, 22.0, 30.0, 18.0];
    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        for (final height in heights)
          Container(
            width: 5,
            height: height,
            margin: const EdgeInsets.symmetric(horizontal: 3),
            decoration: BoxDecoration(
              color: AppChrome.primary.withValues(alpha: 0.42),
              borderRadius: BorderRadius.circular(6),
            ),
          ),
      ],
    );
  }
}

class _QuickPrompts extends StatelessWidget {
  const _QuickPrompts();

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      children: const [
        _PromptChip(icon: Icons.add_alert_rounded, label: 'Create reminder'),
        _PromptChip(icon: Icons.today_rounded, label: 'Today agenda'),
        _PromptChip(icon: Icons.repeat_rounded, label: 'Recurring task'),
      ],
    );
  }
}

class _PromptChip extends StatelessWidget {
  const _PromptChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      borderRadius: 22,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: AppChrome.primary, size: 18),
          const SizedBox(width: 8),
          Text(
            label,
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
        ],
      ),
    );
  }
}

class _VoiceNotesPanel extends StatelessWidget {
  const _VoiceNotesPanel();

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      borderRadius: 26,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: const [
          Text(
            'Voice session preview',
            style: TextStyle(
              color: AppChrome.ink,
              fontSize: 18,
              fontWeight: FontWeight.w800,
            ),
          ),
          SizedBox(height: 10),
          Text(
            'Recognized speech, extracted reminder details, confidence, and confirm actions will live here when the voice module is wired.',
            style: TextStyle(color: AppChrome.muted, height: 1.4),
          ),
        ],
      ),
    );
  }
}
