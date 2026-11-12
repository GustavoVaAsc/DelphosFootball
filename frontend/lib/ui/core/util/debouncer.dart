/// Runs an action once, a fixed delay after the last of a burst of calls
/// (the explorer's search field).
library;

import 'dart:async';

/// Delays [run] until no new call arrives for [delay].
class Debouncer {
  Debouncer(this.delay);

  final Duration delay;
  Timer? _timer;

  /// Whether an action is waiting to run.
  bool get isPending => _timer?.isActive ?? false;

  /// Replaces any waiting action with [action].
  void run(void Function() action) {
    _timer?.cancel();
    _timer = Timer(delay, () {
      _timer = null;
      action();
    });
  }

  /// Drops the waiting action, if any.
  void cancel() {
    _timer?.cancel();
    _timer = null;
  }
}
