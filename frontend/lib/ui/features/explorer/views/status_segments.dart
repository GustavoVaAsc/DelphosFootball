/// The Estado filter: the explorer's primary segmented control
/// (DESIGN.md §4). Its labels match the table pills exactly.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/valuation_status.dart';
import '../../../core/labels/valuation_labels.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/motion.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/pressable.dart';

/// Todos | Infravalorado | En precio | Sobrevalorado.
class StatusSegments extends StatelessWidget {
  const StatusSegments({
    super.key,
    required this.value,
    required this.onChanged,
  });

  final ValuationStatus? value;

  /// `null` disables the control (while the first page loads).
  final ValueChanged<ValuationStatus?>? onChanged;

  @override
  Widget build(BuildContext context) {
    final options = <(ValuationStatus?, String)>[
      (null, 'Todos'),
      for (final status in ValuationStatus.values)
        (status, valuationStatusLabel(status)),
    ];
    return Semantics(
      container: true,
      label: 'Estado',
      child: Opacity(
        opacity: onChanged == null ? 0.5 : 1,
        child: Container(
          padding: const EdgeInsets.all(2),
          decoration: BoxDecoration(
            color: DelphosColors.surface,
            borderRadius: BorderRadius.circular(7),
            border: Border.all(color: DelphosColors.controlBorder),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            spacing: 2,
            children: [
              for (final (status, label) in options)
                _Segment(
                  label: label,
                  active: status == value,
                  onPressed: onChanged == null
                      ? null
                      : () => onChanged!(status),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Segment extends StatelessWidget {
  const _Segment({
    required this.label,
    required this.active,
    required this.onPressed,
  });

  final String label;
  final bool active;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onPressed: onPressed,
      semanticLabel: label,
      selected: active,
      borderRadius: 5,
      builder: (context, hovered) => AnimatedContainer(
        // Hover and selection feedback (DESIGN.md §5).
        duration: DelphosMotion.duration(context, DelphosMotion.hover),
        curve: DelphosMotion.easeOut,
        height: 26,
        padding: const EdgeInsets.symmetric(horizontal: 8),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: active
              ? DelphosColors.ink
              : (hovered ? DelphosColors.surfaceSubtle : null),
          borderRadius: BorderRadius.circular(5),
        ),
        child: Text(
          label,
          maxLines: 1,
          softWrap: false,
          style: DelphosText.ui(
            size: TypeScale.secondary,
            weight: FontWeight.w500,
            color: active
                ? DelphosColors.surface
                : (hovered ? DelphosColors.ink : DelphosColors.ink2),
          ),
        ),
      ),
    );
  }
}
