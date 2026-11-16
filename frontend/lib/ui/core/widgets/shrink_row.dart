/// A one-line row whose children shrink in a stated order when the row is
/// too narrow, decided by layout and not by pre-measuring text.
///
/// Every child is laid out at its natural width first. If the sum, with the
/// gaps, is wider than the row's maximum, children with `shrink: 1` give up
/// width first (down to zero), then those with `shrink: 2`; children with
/// `shrink: 0` never shrink. Children that fit are never touched. A child
/// that can shrink must cope with a narrower maximum (a `Text` with an
/// ellipsis does). Children are centred vertically; the row is as wide as its
/// children and as tall as the tallest.
library;

import 'dart:math' as math;

import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';

/// Parent data of a [ShrinkRow] child.
class ShrinkRowParentData extends ContainerBoxParentData<RenderBox> {
  double gapBefore = 0;
  int shrink = 0;
}

/// Sets a child's gap before it and its shrink order.
class ShrinkItem extends ParentDataWidget<ShrinkRowParentData> {
  const ShrinkItem({
    super.key,
    this.gapBefore = 6,
    this.shrink = 0,
    required super.child,
  });

  final double gapBefore;
  final int shrink;

  @override
  void applyParentData(RenderObject renderObject) {
    final data = renderObject.parentData! as ShrinkRowParentData;
    if (data.gapBefore != gapBefore || data.shrink != shrink) {
      data.gapBefore = gapBefore;
      data.shrink = shrink;
      renderObject.parent?.markNeedsLayout();
    }
  }

  @override
  Type get debugTypicalAncestorWidgetClass => ShrinkRow;
}

/// The row; its children are [ShrinkItem]s.
class ShrinkRow extends MultiChildRenderObjectWidget {
  const ShrinkRow({super.key, super.children});

  @override
  RenderObject createRenderObject(BuildContext context) => _RenderShrinkRow();
}

class _RenderShrinkRow extends RenderBox
    with
        ContainerRenderObjectMixin<RenderBox, ShrinkRowParentData>,
        RenderBoxContainerDefaultsMixin<RenderBox, ShrinkRowParentData> {
  @override
  void setupParentData(RenderBox child) {
    if (child.parentData is! ShrinkRowParentData) {
      child.parentData = ShrinkRowParentData();
    }
  }

  List<RenderBox> get _kids {
    final kids = <RenderBox>[];
    for (var c = firstChild; c != null; c = childAfter(c)) {
      kids.add(c);
    }
    return kids;
  }

  ShrinkRowParentData _data(RenderBox c) =>
      c.parentData! as ShrinkRowParentData;

  @override
  void performLayout() {
    final kids = _kids;
    final natural = BoxConstraints(maxHeight: constraints.maxHeight);
    final widths = <double>[];
    var total = 0.0;
    for (var i = 0; i < kids.length; i++) {
      kids[i].layout(natural, parentUsesSize: true);
      widths.add(kids[i].size.width);
      total += widths[i] + (i > 0 ? _data(kids[i]).gapBefore : 0);
    }
    var overflow = constraints.maxWidth.isFinite
        ? total - constraints.maxWidth
        : 0.0;
    for (final level in const [1, 2]) {
      for (var i = 0; i < kids.length; i++) {
        if (_data(kids[i]).shrink != level || overflow <= 0) continue;
        final cut = math.min(overflow, widths[i]);
        widths[i] -= cut;
        overflow -= cut;
        kids[i].layout(
          BoxConstraints(maxWidth: widths[i], maxHeight: constraints.maxHeight),
          parentUsesSize: true,
        );
      }
    }
    var height = 0.0;
    for (final kid in kids) {
      height = math.max(height, kid.size.height);
    }
    var x = 0.0;
    for (var i = 0; i < kids.length; i++) {
      if (i > 0) x += _data(kids[i]).gapBefore;
      _data(kids[i]).offset = Offset(x, (height - kids[i].size.height) / 2);
      x += kids[i].size.width;
    }
    size = constraints.constrain(Size(x, height));
  }

  @override
  Size computeDryLayout(BoxConstraints constraints) {
    var width = 0.0;
    var height = 0.0;
    var i = 0;
    for (final kid in _kids) {
      final size = kid.getDryLayout(const BoxConstraints());
      width += size.width + (i++ > 0 ? _data(kid).gapBefore : 0);
      height = math.max(height, size.height);
    }
    return constraints.constrain(Size(width, height));
  }

  @override
  void paint(PaintingContext context, Offset offset) =>
      defaultPaint(context, offset);

  @override
  bool hitTestChildren(BoxHitTestResult result, {required Offset position}) =>
      defaultHitTestChildren(result, position: position);
}
