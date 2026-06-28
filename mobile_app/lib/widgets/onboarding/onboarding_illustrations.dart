import 'dart:math' as math;

import 'package:flutter/material.dart';
import '../app_chrome.dart';

enum OnboardingIllustrationKind { welcome, chat, notifications, voice }

class OnboardingIllustration extends StatefulWidget {
  final OnboardingIllustrationKind kind;
  final bool animate;

  const OnboardingIllustration({
    super.key,
    required this.kind,
    this.animate = true,
  });

  @override
  State<OnboardingIllustration> createState() => _OnboardingIllustrationState();
}

class _OnboardingIllustrationState extends State<OnboardingIllustration>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _scale;
  late final Animation<double> _float;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2200),
    );
    _scale = Tween<double>(begin: 0.88, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.elasticOut),
    );
    _float = Tween<double>(begin: -8, end: 8).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
    if (widget.animate) {
      _controller.repeat(reverse: true);
    } else {
      _controller.value = 1;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Transform.translate(
          offset: Offset(0, _float.value),
          child: Transform.scale(
            scale: widget.animate ? _scale.value : 1,
            child: child,
          ),
        );
      },
      child: _buildIllustration(),
    );
  }

  Widget _buildIllustration() {
    switch (widget.kind) {
      case OnboardingIllustrationKind.welcome:
        return _iconCluster(
          primary: Icons.alarm_rounded,
          secondary: Icons.auto_awesome,
          ringColor: AppChrome.primary.withValues(alpha: 0.22),
        );
      case OnboardingIllustrationKind.chat:
        return _chatBubbles();
      case OnboardingIllustrationKind.notifications:
        return _iconCluster(
          primary: Icons.notifications_active_rounded,
          secondary: Icons.schedule_rounded,
          ringColor: AppChrome.accent.withValues(alpha: 0.22),
        );
      case OnboardingIllustrationKind.voice:
        return _voiceWaves();
    }
  }

  Widget _iconCluster({
    required IconData primary,
    required IconData secondary,
    required Color ringColor,
  }) {
    return SizedBox(
      height: 200,
      width: 200,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            height: 180,
            width: 180,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: ringColor.withValues(alpha: 0.6), width: 3),
            ),
          ),
          Container(
            height: 140,
            width: 140,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.white.withValues(alpha: 0.92),
              boxShadow: [
                BoxShadow(
                  color: AppChrome.primary.withValues(alpha: 0.25),
                  blurRadius: 28,
                  offset: const Offset(0, 12),
                ),
              ],
            ),
            child: Icon(primary, size: 72, color: AppChrome.primary),
          ),
          Positioned(
            right: 18,
            top: 24,
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppChrome.primary,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(secondary, color: Colors.white, size: 26),
            ),
          ),
        ],
      ),
    );
  }

  Widget _chatBubbles() {
    return SizedBox(
      height: 220,
      width: 280,
      child: Stack(
        children: [
          _bubble(
            left: 0,
            top: 40,
            text: 'Remind me to call mom\nat 8 PM tomorrow',
            alignEnd: false,
          ),
          _bubble(
            right: 0,
            bottom: 20,
            text: "Got it! I'll remind you.",
            alignEnd: true,
          ),
        ],
      ),
    );
  }

  Widget _bubble({
    double? left,
    double? right,
    double? top,
    double? bottom,
    required String text,
    required bool alignEnd,
  }) {
    return Positioned(
      left: left,
      right: right,
      top: top,
      bottom: bottom,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 200),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: alignEnd
              ? AppChrome.primary
              : Colors.white.withValues(alpha: 0.95),
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(20),
            topRight: const Radius.circular(20),
            bottomLeft: Radius.circular(alignEnd ? 20 : 4),
            bottomRight: Radius.circular(alignEnd ? 4 : 20),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.08),
              blurRadius: 16,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Text(
          text,
          style: TextStyle(
            color: alignEnd ? Colors.white : Colors.black87,
            fontSize: 14,
            height: 1.35,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }

  Widget _voiceWaves() {
    return SizedBox(
      height: 200,
      width: 200,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          final t = _controller.value;
          return Stack(
            alignment: Alignment.center,
            children: [
              for (var i = 0; i < 3; i++)
                Container(
                  height: 120 + i * 28 + math.sin(t * math.pi * 2 + i) * 6,
                  width: 120 + i * 28 + math.sin(t * math.pi * 2 + i) * 6,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: Colors.white.withValues(alpha: 0.35 - i * 0.08),
                      width: 2,
                    ),
                  ),
                ),
              Container(
                height: 100,
                width: 100,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.white.withValues(alpha: 0.95),
                  boxShadow: [
                    BoxShadow(
                      color: AppChrome.primary.withValues(alpha: 0.3),
                      blurRadius: 24,
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.mic_rounded,
                  size: 52,
                  color: AppChrome.primary,
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
