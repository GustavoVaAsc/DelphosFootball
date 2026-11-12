/// The comparator's player selector (DESIGN.md §4): a search field with a
/// list of up to ten suggestions under it. Down and Up move the highlight,
/// Enter picks the highlighted player, Escape closes the list; a click
/// picks too. Focus stays in the field the whole time.
library;

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

import '../view_models/player_search_view_model.dart';
import 'selector_field.dart';
import 'selector_suggestions.dart';

/// The search field and its suggestion overlay.
class PlayerSelector extends StatefulWidget {
  const PlayerSelector({super.key, required this.vm, required this.onPick});

  final PlayerSearchViewModel vm;

  /// Called with the chosen player's id.
  final ValueChanged<int> onPick;

  @override
  State<PlayerSelector> createState() => _PlayerSelectorState();
}

class _PlayerSelectorState extends State<PlayerSelector> {
  final OverlayPortalController _overlay = OverlayPortalController();
  final LayerLink _link = LayerLink();
  final TextEditingController _text = TextEditingController();
  final FocusNode _focus = FocusNode(debugLabel: 'player selector');

  static const double width = 320;

  @override
  void initState() {
    super.initState();
    widget.vm.addListener(_syncOverlay);
  }

  /// Shows the list while the search is open (from a listener, never from
  /// build, where showing an overlay is not allowed).
  void _syncOverlay() {
    if (widget.vm.isOpen && !_overlay.isShowing) _overlay.show();
    if (!widget.vm.isOpen && _overlay.isShowing) _overlay.hide();
  }

  @override
  void dispose() {
    widget.vm.removeListener(_syncOverlay);
    _text.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _pick(int playerId) {
    _text.clear();
    widget.vm.setText('');
    widget.onPick(playerId);
  }

  KeyEventResult _onKey(FocusNode node, KeyEvent event) {
    if (event is! KeyDownEvent && event is! KeyRepeatEvent) {
      return KeyEventResult.ignored;
    }
    final vm = widget.vm;
    switch (event.logicalKey) {
      case LogicalKeyboardKey.arrowDown when vm.isOpen:
        vm.moveHighlight(1);
      case LogicalKeyboardKey.arrowUp when vm.isOpen:
        vm.moveHighlight(-1);
      case LogicalKeyboardKey.enter || LogicalKeyboardKey.numpadEnter
          when vm.highlightedPlayer != null:
        _pick(vm.highlightedPlayer!.id);
      case LogicalKeyboardKey.escape when vm.isOpen:
        vm.close();
      default:
        return KeyEventResult.ignored;
    }
    return KeyEventResult.handled;
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: Listenable.merge([widget.vm, _focus]),
      builder: (context, _) {
        final vm = widget.vm;
        return CompositedTransformTarget(
          link: _link,
          child: OverlayPortal(
            controller: _overlay,
            overlayChildBuilder: (context) => CompositedTransformFollower(
              link: _link,
              targetAnchor: Alignment.bottomLeft,
              offset: const Offset(0, 4),
              child: Align(
                alignment: Alignment.topLeft,
                child: SelectorSuggestions(vm: vm, width: width, onPick: _pick),
              ),
            ),
            child: Focus(
              onKeyEvent: _onKey,
              skipTraversal: true,
              child: SelectorField(
                controller: _text,
                focusNode: _focus,
                onChanged: vm.setText,
                width: width,
              ),
            ),
          ),
        );
      },
    );
  }
}
