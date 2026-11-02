"""Resolve historical quest costume stat bonuses through native ability rows."""
import json
from collections import defaultdict

TABLES=['m_costume','m_quest_bonus_character_group','m_quest_bonus_costume_group','m_quest_bonus_costume_setting_group','m_quest_bonus_ability',
        'm_ability','m_ability_level_group','m_ability_detail','m_ability_behaviour_group',
        'm_ability_behaviour','m_abiliwy_behaviour','m_ability_behaviour_action_status','m_ability_status']


def grouped(rows):
    d=defaultdict(list)
    for r in rows:d[r[0]].append(r)
    return d


def ability_stats(tables,effect_group,groups):
    """Only unconditional permil stat-up actions, with complete foreign keys."""
    totals=defaultdict(float);proof=[]
    for effect in groups['m_quest_bonus_effect_group'][effect_group]:
        if effect[2]!=1:continue
        for ab in groups['m_quest_bonus_ability'][effect[3]]:
            ability=groups['m_ability'][ab[1]]
            if len(ability)!=1:return None
            levels=[r for r in groups['m_ability_level_group'][ability[0][1]] if r[1]<=ab[2]]
            if not levels:return None
            level=max(levels,key=lambda r:r[1]);detail=groups['m_ability_detail'][level[2]]
            if len(detail)!=1:return None
            for bg in groups['m_ability_behaviour_group'][detail[0][3]]:
                behaviours=groups['m_ability_behaviour'][bg[2]] or groups['m_abiliwy_behaviour'][bg[2]]
                if len(behaviours)!=1:return None
                behaviour=behaviours[0]
                if behaviour[1]!=3:continue
                actions=groups['m_ability_behaviour_action_status'][behaviour[2]]
                if len(actions)!=1:return None
                action=actions[0]
                # Multiply (permil), any attribute, ordinary in-deck condition.
                # Conditional/flat actions need separate decoding and are omitted.
                if action[1:4]!=[2,8,4]:return None
                statuses=groups['m_ability_status'][action[4]]
                if len(statuses)!=1:return None
                status=statuses[0]
                if any(status[i] for i in [3,4,5]):return None
                for index,name in [(1,'Agility'),(2,'Attack'),(6,'HP'),(7,'Defense')]:
                    if status[index]:totals[name]+=status[index]/10
                proof.append({'quest_effect':effect,'quest_ability':ab,'ability':ability[0],
                              'level':level,'detail':detail[0],'behaviour_group':bg,
                              'behaviour':behaviour,'action':action,'status':status})
    return ({k:int(v) if v.is_integer() else v for k,v in totals.items()},proof) if totals else None


def recover_costume_bonuses(tables,bonus_ids,costumes,start,end):
    names=TABLES+['m_quest_bonus','m_quest_bonus_effect_group','m_quest_bonus_term_group']
    groups={name:grouped(tables.get(name,[])) for name in names}
    result=[]
    for ident in sorted(costumes):
        candidates=[]
        for bid in bonus_ids:
            for bonus in groups['m_quest_bonus'][bid]:
                modern=groups['m_quest_bonus_costume_setting_group'][bonus[4]] if len(bonus)>4 and bonus[4] else []
                matches=[r for r in modern if r[1]==ident]
                if matches:candidates.append([(r[2],r[3],r[4] if len(r)>4 else 0,r) for r in matches])
                else:
                    old=[r for r in groups['m_quest_bonus_costume_group'][bonus[2]] if r[1]==ident]
                    if old:candidates.append([(0,r[2],r[3] if len(r)>3 else 0,r) for r in old])
                    else:
                        costume=groups['m_costume'][ident]
                        if len(costume)==1:
                            character=[r for r in groups['m_quest_bonus_character_group'][bonus[1]] if r[1]==costume[0][1]]
                            if character:candidates.append([(0,r[2],r[3] if len(r)>3 else 0,r) for r in character])
        variants={}
        for rows in {json.dumps(rows):rows for rows in candidates}.values():
            active=[]
            for threshold,fx,term,row in rows:
                terms=groups['m_quest_bonus_term_group'][term]
                if term and not any(r[2]<=start and r[3]>=end for r in terms):continue
                active.append((threshold,fx,row))
            ascension=[];proof=[]
            for count in range(5):
                available=[r for r in active if r[0]<=count]
                if not available:break
                chosen=max(available,key=lambda r:r[0]);decoded=ability_stats(tables,chosen[1],groups)
                if not decoded:break
                stats,ability_proof=decoded;ascension.append(stats)
                proof.append({'costume_bonus_row':chosen[2],'ability_chain':ability_proof})
            if len(ascension)!=5:continue
            stats={k:[a.get(k,0) for a in ascension] for k in sorted(set().union(*(a.keys() for a in ascension)))}
            variants[json.dumps(stats,sort_keys=True)]={'costume_id':ident,'stat_percent_by_ascension':stats,
                                                      'start':start,'end':end,'native_rows':proof}
        # Different quest groups can have different effects; do not conflate
        # them into a chapter-wide value without recovering their quest scope.
        if len(variants)==1:result.append(next(iter(variants.values())))
    return result
