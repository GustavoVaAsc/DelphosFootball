/// The explorer's search input (DESIGN.md §4, Filter bar). The backend
/// matches word prefixes across player name, club and country, so the
/// placeholder reads "Buscar jugador, club o país". Escape with text clears
/// the field first; Escape on an empty field closes the dossier.
library;

import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../../../../routing/explorer_query.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/widgets/focus_ring.dart';
import '../../../core/widgets/line_glyph.dart';

/// A 240 x 32 search box with the magnifier and the ink focus ring. It has a
/// placeholder and an accessible label, and no visible label (an explicit
/// exception, DESIGN.md §4).
class SearchField extends StatefulWidget {
  const SearchField({
    super.key,
    required this.text,
    required this.onChanged,
    required this.enabled,
    required this.focusNode,
  });

  static const double width = 240;

  /// The live text from the ViewModel (it changes on "Restablecer").
  final String text;
  final ValueChanged<String> onChanged;
  final bool enabled;
  final FocusNode focusNode;

  @override
  State<SearchField> createState() => _SearchFieldState();
}

class _SearchFieldState extends State<SearchField> {
  late final TextEditingController _controller = TextEditingController(
    text: widget.text,
  );

  @override
  void didUpdateWidget(SearchField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.text != _controller.text) _controller.text = widget.text;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  KeyEventResult _onKey(FocusNode node, KeyEvent event) {
    if (event is KeyDownEvent &&
        event.logicalKey == LogicalKeyboardKey.escape &&
        _controller.text.isNotEmpty) {
      _controller.clear();
      widget.onChanged('');
      return KeyEventResult.handled;
    }
    return KeyEventResult.ignored;
  }

  @override
  Widget build(BuildContext context) {
    final style = DelphosText.ui();
    return Focus(
      onKeyEvent: _onKey,
      skipTraversal: true,
      child: ListenableBuilder(
        listenable: widget.focusNode,
        builder: (context, _) => FocusRing(
          visible: widget.focusNode.hasFocus,
          borderRadius: DelphosRadius.control,
          child: Container(
            width: SearchField.width,
            height: 32,
            decoration: BoxDecoration(
              color: DelphosColors.surface,
              borderRadius: BorderRadius.circular(DelphosRadius.control),
              border: Border.all(color: DelphosColors.controlBorder),
            ),
            child: Row(
              children: [
                const Padding(
                  padding: EdgeInsets.only(left: 10, right: 6),
                  child: LineGlyph.search(),
                ),
                Expanded(
                  child: Semantics(
                    label: 'Buscar jugador, club o país',
                    child: TextField(
                      controller: _controller,
                      focusNode: widget.focusNode,
                      enabled: widget.enabled,
                      onChanged: widget.onChanged,
                      style: style,
                      cursorColor: DelphosColors.ink,
                      inputFormatters: [
                        LengthLimitingTextInputFormatter(
                          ExplorerQuery.maxSearchLength,
                        ),
                      ],
                      decoration: InputDecoration.collapsed(
                        hintText: 'Buscar jugador, club o país',
                        hintStyle: style.copyWith(color: DelphosColors.ink3),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
