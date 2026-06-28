import 'dart:ui';

import 'package:flutter/material.dart';

class AppChrome {
  static const Color primary = Color(0xFF6366F1);
  static const Color accent = Color(0xFF14B8A6);
  static const Color ink = Color(0xFF111827);
  static const Color muted = Color(0xFF64748B);
  static const Color surface = Color(0xFFF8FAFC);
  static const Color line = Color(0xFFE2E8F0);

  static BoxDecoration backgroundDecoration() {
    return const BoxDecoration(
      gradient: RadialGradient(
        center: Alignment.topRight,
        radius: 1.2,
        colors: [
          Color(0xFFEFF6FF),
          Color(0xFFF8FAFC),
          Color(0xFFF7F7F4),
        ],
        stops: [0, 0.55, 1],
      ),
    );
  }

  static ButtonStyle primaryButtonStyle() {
    return FilledButton.styleFrom(
      backgroundColor: primary,
      foregroundColor: Colors.white,
      padding: const EdgeInsets.symmetric(vertical: 15, horizontal: 18),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
    );
  }

  static InputDecoration inputDecoration({
    required String label,
    String? hint,
    String? helperText,
    Widget? prefixIcon,
  }) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      helperText: helperText,
      prefixIcon: prefixIcon,
      filled: true,
      fillColor: Colors.white.withValues(alpha: 0.72),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: const BorderSide(color: line),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: BorderSide(color: line.withValues(alpha: 0.8)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: const BorderSide(color: primary, width: 1.5),
      ),
    );
  }
}

class SpeakardoScaffold extends StatelessWidget {
  const SpeakardoScaffold({
    super.key,
    required this.child,
    this.safeArea = true,
    this.bottomNavigationBar,
    this.appBar,
  });

  final Widget child;
  final bool safeArea;
  final Widget? bottomNavigationBar;
  final PreferredSizeWidget? appBar;

  @override
  Widget build(BuildContext context) {
    final content = Container(
      decoration: AppChrome.backgroundDecoration(),
      child: Stack(
        children: [
          const Positioned.fill(child: _GridBackdrop()),
          if (safeArea) SafeArea(child: child) else child,
        ],
      ),
    );

    return Scaffold(
      extendBody: true,
      backgroundColor: AppChrome.surface,
      appBar: appBar,
      body: content,
      bottomNavigationBar: bottomNavigationBar,
    );
  }
}

class _GridBackdrop extends StatelessWidget {
  const _GridBackdrop();

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _GridPainter());
  }
}

class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppChrome.line.withValues(alpha: 0.35)
      ..strokeWidth = 0.7;
    const step = 32.0;
    for (double x = 0; x <= size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y <= size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class GlassPanel extends StatelessWidget {
  const GlassPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.borderRadius = 24,
    this.color,
    this.borderColor,
    this.margin,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double borderRadius;
  final Color? color;
  final Color? borderColor;
  final EdgeInsetsGeometry? margin;

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(borderRadius);
    return Container(
      margin: margin,
      child: ClipRRect(
        borderRadius: radius,
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
          child: Container(
            padding: padding,
            decoration: BoxDecoration(
              color: color ?? Colors.white.withValues(alpha: 0.68),
              borderRadius: radius,
              border: Border.all(
                color: borderColor ?? Colors.white.withValues(alpha: 0.78),
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.04),
                  blurRadius: 24,
                  offset: const Offset(0, 12),
                ),
              ],
            ),
            child: child,
          ),
        ),
      ),
    );
  }
}

class AppLogoMark extends StatelessWidget {
  const AppLogoMark({super.key, this.size = 42});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: Colors.white,
        border: Border.all(color: AppChrome.primary.withValues(alpha: 0.12)),
        boxShadow: [
          BoxShadow(
            color: AppChrome.primary.withValues(alpha: 0.14),
            blurRadius: 18,
          ),
        ],
      ),
      child: Center(
        child: Container(
          width: size * 0.52,
          height: size * 0.52,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                AppChrome.primary.withValues(alpha: 0.45),
                Colors.white,
                AppChrome.accent.withValues(alpha: 0.4),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class SpeakardoTopBar extends StatelessWidget {
  const SpeakardoTopBar({
    super.key,
    required this.title,
    this.subtitle,
    this.leading,
    this.trailing,
    this.padding = const EdgeInsets.fromLTRB(20, 16, 20, 12),
  });

  final String title;
  final String? subtitle;
  final Widget? leading;
  final Widget? trailing;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: padding,
      child: Row(
        children: [
          leading ?? const AppLogoMark(),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppChrome.ink,
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 3),
                  Text(
                    subtitle!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppChrome.muted,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

class RevampedBottomNav extends StatelessWidget {
  const RevampedBottomNav({
    super.key,
    required this.currentIndex,
    required this.onTap,
  });

  final int currentIndex;
  final ValueChanged<int> onTap;

  static const _items = [
    _NavItem('Chat', Icons.chat_bubble_outline, Icons.chat_bubble),
    _NavItem('Timeline', Icons.calendar_month_outlined, Icons.calendar_month),
    _NavItem('Mic', Icons.mic_none_rounded, Icons.mic_rounded),
    _NavItem('Memory', Icons.psychology_alt_outlined, Icons.psychology_alt),
    _NavItem('System', Icons.settings_outlined, Icons.settings),
  ];

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
      child: GlassPanel(
        borderRadius: 28,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: List.generate(_items.length, (index) {
            final item = _items[index];
            final active = index == currentIndex;
            final isMic = index == 2;
            return Expanded(
              child: InkWell(
                borderRadius: BorderRadius.circular(22),
                onTap: () => onTap(index),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 220),
                  curve: Curves.easeOutCubic,
                  height: 58,
                  decoration: BoxDecoration(
                    color: active && !isMic
                        ? AppChrome.primary.withValues(alpha: 0.08)
                        : Colors.transparent,
                    borderRadius: BorderRadius.circular(22),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      AnimatedContainer(
                        duration: const Duration(milliseconds: 220),
                        width: isMic ? 48 : 28,
                        height: isMic ? 48 : 28,
                        decoration: isMic
                            ? BoxDecoration(
                                shape: BoxShape.circle,
                                color: AppChrome.primary,
                                border: Border.all(
                                  color: Colors.white,
                                  width: 3,
                                ),
                                boxShadow: [
                                  BoxShadow(
                                    color: AppChrome.primary.withValues(
                                      alpha: active ? 0.36 : 0.22,
                                    ),
                                    blurRadius: 20,
                                    offset: const Offset(0, 8),
                                  ),
                                ],
                              )
                            : null,
                        child: Icon(
                          active ? item.activeIcon : item.icon,
                          size: isMic ? 23 : 22,
                          color: isMic
                              ? Colors.white
                              : active
                                  ? AppChrome.primary
                                  : AppChrome.muted,
                        ),
                      ),
                      if (!isMic) ...[
                        const SizedBox(height: 1),
                        Text(
                          item.label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: active ? AppChrome.primary : AppChrome.muted,
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            );
          }),
        ),
      ),
    );
  }
}

class _NavItem {
  const _NavItem(this.label, this.icon, this.activeIcon);

  final String label;
  final IconData icon;
  final IconData activeIcon;
}
