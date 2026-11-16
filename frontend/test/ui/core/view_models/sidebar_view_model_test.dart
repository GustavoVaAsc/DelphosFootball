// Tests for the sidebar's in-memory collapsed flag.
import 'package:delphos_frontend/ui/core/view_models/sidebar_view_model.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('starts open and toggles back and forth, notifying each time', () {
    final vm = SidebarViewModel();
    var notifications = 0;
    vm.addListener(() => notifications++);

    expect(vm.collapsed, isFalse);
    vm.toggle();
    expect(vm.collapsed, isTrue);
    vm.toggle();
    expect(vm.collapsed, isFalse);
    expect(notifications, 2);
  });
}
