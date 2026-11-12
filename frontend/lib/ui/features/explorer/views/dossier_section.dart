/// One section of the dossier body (DESIGN.md §4): a title with an optional
/// subtitle, an optional action on its own line under them (beside the
/// title it squeezed the subtitle onto two lines at 440 px), then the
/// content. Sections are separated by
/// hairlines and spacing, never nested cards (DESIGN.md §5).
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';

/// A titled block with a hairline above it (none for the first).
class DossierSection extends StatelessWidget {
  const DossierSection({
    super.key,
    required this.title,
    required this.child,
    this.subtitle,
    this.action,
    this.first = false,
  });

  /// `null` for the valuation, which opens the body without a title.
  final String? title;
  final String? subtitle;
  final Widget? action;
  final Widget child;
  final bool first;

  @override
  Widget build(BuildContext context) {
    final subtitleStyle = DelphosText.ui(
      size: TypeScale.secondary,
      color: DelphosColors.ink3,
    );
    final heading = title == null
        ? null
        : Semantics(
            header: true,
            child: Text(
              title!,
              style: DelphosText.ui(
                size: TypeScale.section,
                weight: FontWeight.w700,
              ),
            ),
          );
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16),
      decoration: BoxDecoration(
        border: first
            ? null
            : const Border(top: BorderSide(color: DelphosColors.rule)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        spacing: 12,
        children: [
          if (heading != null && action == null)
            Wrap(
              spacing: 12,
              crossAxisAlignment: WrapCrossAlignment.end,
              children: [
                heading,
                if (subtitle != null) Text(subtitle!, style: subtitleStyle),
              ],
            ),
          if (heading != null && action != null)
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              spacing: 10,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    heading,
                    if (subtitle != null) Text(subtitle!, style: subtitleStyle),
                  ],
                ),
                action!,
              ],
            ),
          child,
        ],
      ),
    );
  }
}
