import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Slowly shifting gradient orbs behind onboarding pages.
class AnimatedGradientBackground extends StatefulWidget {
  final Widget child;
  final List<Color> colors;

  const AnimatedGradientBackground({
    super.key,
    required this.child,
    this.colors = const [
      Color(0xFF4F46E5),
      Color(0xFF6366F1),
      Color(0xFF818CF8),
    ],
  });

  @override
  State<AnimatedGradientBackground> createState() =>
      _AnimatedGradientBackgroundState();
}

class _AnimatedGradientBackgroundState extends State<AnimatedGradientBackground>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 8),
    )..repeat(reverse: true);
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
        final t = _controller.value;
        return Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment(-1 + t, -1),
              end: Alignment(1 - t, 1),
              colors: widget.colors,
            ),
          ),
          child: CustomPaint(
            painter: _OrbPainter(progress: t),
            child: child,
          ),
        );
      },
      child: widget.child,
    );
  }
}

class _OrbPainter extends CustomPainter {
  final double progress;

  _OrbPainter({required this.progress});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..style = PaintingStyle.fill;

    void orb(double x, double y, double radius, Color color) {
      paint.color = color.withValues(alpha: 0.22);
      canvas.drawCircle(Offset(x, y), radius, paint);
    }

    final w = size.width;
    final h = size.height;
    final wave = math.sin(progress * math.pi * 2);

    orb(w * 0.15, h * 0.2 + wave * 24, 90, Colors.white);
    orb(w * 0.85, h * 0.35 - wave * 20, 110, const Color(0xFF2DD4BF));
    orb(w * 0.5, h * 0.75 + wave * 16, 130, Colors.white);
  }

  @override
  bool shouldRepaint(covariant _OrbPainter oldDelegate) {
    return oldDelegate.progress != progress;
  }
}
