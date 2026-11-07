# Cython declarations for the bake's compiled copy of deckbuilder/sim/battle.py (the source is unchanged).
# Used by scripts/bake_deckbuilder.py (compiled()): fields of the unit and battle classes, and the hot methods.
cimport cython

cdef class U:
    cdef public object t, side, slot, cid, elem, st, bf, w, comp, na, first_act, died_at, cs_ready, lock
    cdef public double maxhp, atk, df, hp, agi_bonus, team_atk, team_def, team_crit, team_cdmg, gauge, gmult, wmult
    cdef public bint alive

cpdef object _bsum(U x, object k)

cdef class Battle:
    cdef public object sides, rng, log, combo, first_kill, batch_left, comp_events, blocked, first_ben, _pending, attacker_manual
    cdef public double t, frames
    cdef public bint logging, _combo_target
    cdef public long chance_draws
    cdef public bint mirror_safe
    cdef public long na_done
    cdef dict __dict__

    cpdef list allies(self, U u)
    cpdef list enemies(self, U u)
    cpdef object has(self, U u, object key)
    cpdef object agility(self, U u)
    @cython.locals(atk=cython.double, crit=cython.double, cd=cython.double, m=cython.double, add=cython.double,
                   r=cython.double, dfv=cython.double, dmg=cython.double)
    cpdef object hit(self, U u, U tgt, object power, object hits_in_skill, object normal=*, object pierce=*, object comp_atk=*)
    @cython.locals(u=U)
    cpdef object tick(self, object S)
    cpdef object na_interval(self, U u)
    cpdef object start_passives(self, U u)
    cpdef object reliance(self, U e)
    cpdef object run_opening(self)
