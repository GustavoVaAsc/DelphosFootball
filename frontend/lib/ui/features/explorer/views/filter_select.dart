/// A labelled select of the filter bar (Posición, Arquetipo). Built on
/// Material's DropdownButton, which opens with Enter or Space, moves with
/// the arrow keys and closes with Escape; it gets the ink focus ring here.
library;

import 'package:material_ui/material_ui.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/focus_ring.dart';
import '../../../core/widgets/focus_visibility.dart';
import '../../../core/widgets/line_glyph.dart';

/// "Label [value v]" with the options as (value, Spanish label) pairs.
class FilterSelect<T> extends StatefulWidget {
  const FilterSelect({
    super.key,
    required this.label,
    required this.value,
    required this.options,
    required this.onChanged,
  });

  final String label;
  final T? value;

  /// The first option is the "all" choice, with a `null` value.
  final List<(T?, String)> options;

  /// `null` disables the select (while the first page loads).
  final ValueChanged<T?>? onChanged;

  @override
  State<FilterSelect<T>> createState() => _FilterSelectState<T>();
}

class _FilterSelectState<T> extends State<FilterSelect<T>> {
  final FocusNode _focus = FocusNode(debugLabel: 'filter select');

  @override
  void dispose() {
    _focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final valueStyle = DelphosText.ui(weight: FontWeight.w500);
    return Row(
      mainAxisSize: MainAxisSize.min,
      spacing: 8,
      children: [
        ExcludeSemantics(
          child: Text(
            widget.label,
            style: DelphosText.ui(
              size: TypeScale.secondary,
              weight: FontWeight.w500,
              color: DelphosColors.ink3,
            ),
          ),
        ),
        ListenableBuilder(
          listenable: Listenable.merge([_focus, FocusVisibility.keyboard]),
          builder: (context, child) => FocusRing(
            visible: _focus.hasFocus && FocusVisibility.keyboard.value,
            borderRadius: 7,
            child: child!,
          ),
          child: Opacity(
            opacity: widget.onChanged == null ? 0.5 : 1,
            child: Container(
              height: 32,
              padding: const EdgeInsets.only(left: 10, right: 6),
              decoration: BoxDecoration(
                color: DelphosColors.surface,
                borderRadius: BorderRadius.circular(7),
                border: Border.all(color: DelphosColors.controlBorder),
              ),
              child: Semantics(
                label: widget.label,
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<T?>(
                    value: widget.value,
                    focusNode: _focus,
                    focusColor: const Color(0x00000000),
                    isDense: true,
                    style: valueStyle,
                    // The default arrow is a Material icon; the app ships no
                    // icon font, so it draws its own chevron.
                    icon: const Padding(
                      padding: EdgeInsets.only(left: 6),
                      child: LineGlyph.chevronDown(),
                    ),
                    dropdownColor: DelphosColors.surface,
                    borderRadius: BorderRadius.circular(7),
                    onChanged: widget.onChanged,
                    items: [
                      for (final (value, label) in widget.options)
                        DropdownMenuItem<T?>(
                          value: value,
                          child: Text(label, style: valueStyle),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
