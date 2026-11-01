; Irreducible two-entry cycle, unreachable cycle and a direct call with stale
; effect attributes. No Remill helper calls can provide accidental barriers.
define ptr @sub_100(ptr nocapture readnone %state, i64 %pc, ptr %memory) nounwind nosync willreturn memory(none) {
entry:
  %which = and i64 %pc, 4
  %select = icmp eq i64 %which, 0
  br i1 %select, label %a, label %b
a:
  %x = phi i64 [ 0, %entry ], [ %bn, %b ]
  %an = add i64 %x, 1
  %adone = icmp eq i64 %an, 1000
  br i1 %adone, label %done, label %b
b:
  %y = phi i64 [ 0, %entry ], [ %an, %a ]
  %bn = add i64 %y, 1
  %bdone = icmp eq i64 %bn, 1000
  br i1 %bdone, label %done, label %a
done:
  ret ptr %memory
dead1:
  br label %dead2
dead2:
  br label %dead1
}

define ptr @sub_200(ptr %state, i64 %pc, ptr %memory) nounwind nosync willreturn memory(none) {
entry:
  %result = call ptr @sub_100(ptr %state, i64 %pc, ptr %memory) nounwind nosync willreturn memory(none)
  ret ptr %result
}
