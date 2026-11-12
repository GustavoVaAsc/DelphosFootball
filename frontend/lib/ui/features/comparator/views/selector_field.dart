/// The comparator selector's search field (DESIGN.md §4): a 36 px control
/// with the search glyph and the "Buscar jugador" hint, and a focus ring
/// while it has focus. The keys and the suggestion list belong to
/// `PlayerSelector`; this file only draws the field.
library;

import 'package:material_ui/material_ui.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/widgets/focus_ring.dart';
import '../../../core/widgets/line_glyph.dart';

/// The selector's text field.
class SelectorField extends StatelessWidget {
  const SelectorField({
    super.key,
    required this.controller,
    required this.focusNode,
    required this.onChanged,
    required this.width,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final ValueChanged<String> onChanged;
  final double width;

  @override
  Widget build(BuildContext context) {
    final style = DelphosText.ui();
    return FocusRing(
      visible: focusNode.hasFocus,
      borderRadius: 7,
      child: Container(
        width: width,
        height: 36,
        decoration: BoxDecoration(
          color: DelphosColors.surface,
          borderRadius: BorderRadius.circular(7),
          border: Border.all(color: DelphosColors.controlBorder),
        ),
        child: Row(
          children: [
            const Padding(
              padding: EdgeInsets.only(left: 10, right: 6),
              child: LineGlyph.search(),
            ),
            Expanded(
              child: TextField(
                controller: controller,
                focusNode: focusNode,
                onChanged: onChanged,
                style: style,
                cursorColor: DelphosColors.ink,
                decoration: InputDecoration.collapsed(
                  hintText: 'Buscar jugador',
                  hintStyle: style.copyWith(color: DelphosColors.ink3),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
