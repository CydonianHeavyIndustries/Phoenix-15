//------------------------------------------------------------
// TitanCommander : movement / combat / puppet helpers
//------------------------------------------------------------

function TitanMoveTo(titan, pos)
{
    if (!pos)
        return;
    local dist = Distance(titan.GetOrigin(), pos);
    if (dist > 150)
        titan.MoveTowards(pos);
    else
        titan.Stop();
}

function TitanAttack(titan, target)
{
    if (!IsValid(target))
    {
        titan.Stop();
        return;
    }
    titan.SetEnemy(target);
    titan.ShootAt(target);
}

// Simplified puppet input (manual override)
function TitanApplyPuppetInput(titan, input)
{
    if (!input)
        return;

    // movement
    local fwd = titan.GetForwardVector();
    local right = titan.GetRightVector();
    local move = (fwd * (input.forward ? input.forward.tofloat() : 0.0)) +
                 (right * (input.strafe ? input.strafe.tofloat() : 0.0));
    titan.SetVelocity(move * titan.GetMaxSpeed());

    // aim
    if ("pitch" in input && "yaw" in input)
        titan.SetAngles(Vector(input.pitch, input.yaw, 0));

    // fire / ability (placeholder hooks; you can map to specific abilities per loadout)
    if ("fire" in input && input.fire)
        titan.FireWeapon();
    if ("ability" in input && input.ability)
        TitanUseMappedAbility(titan, input.ability);
    if ("core" in input && input.core)
        titan.UseCore();
}

// Ability name mapper (Ronin-oriented; falls back to generic use)
function TitanUseMappedAbility(titan, ability)
{
    if (!ability) return;
    local a = ability.tolower();
    // Common Ronin tokens
    if (a == "ronin_block" || a == "block" || a == "swordblock")
    {
        titan.UseAbility("sword_block");
        return;
    }
    if (a == "ronin_phase" || a == "phase" || a == "phase_dash")
    {
        titan.UseAbility("phase_dash");
        return;
    }
    if (a == "ronin_dash" || a == "dash")
    {
        titan.UseAbility("dash");
        return;
    }
    // Fallback: attempt direct ability name
    titan.UseAbility(ability);
}
