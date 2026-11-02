#pragma once
// Included after SignalHost, including inside the bootstrap's anonymous namespace.
// Only mask/action admission: no provider calls, mutation, queueing or delivery.
struct GameCollectorWaitMask {
  using Host=bunker::windows::SignalHost;
  static bool Ordinary(uint64_t mask){return !(mask&(Host::Bit(30)|Host::Bit(24)));}
  static bool SelectedStop(uint64_t token,uint64_t current,const Host::Delivery &selected){
    const uint64_t unblockable=Host::Bit(9)|Host::Bit(19);
    const uint64_t original_action_mask=~(Host::Bit(2)|Host::Bit(3)|Host::Bit(6)|Host::Bit(15)|unblockable);
    return selected.token==token&&selected.signal==30&&Ordinary(selected.saved_mask)&&
      selected.action.handler==0x825beb3c&&selected.action.flags==0x10000004&&selected.action.mask==original_action_mask&&
      current==((selected.saved_mask|selected.action.mask|Host::Bit(30))&~unblockable);
  }
};
