# (shortened header) See chat for details.
import math
from typing import Dict, Any, List

def _ceil_hours(minutes: int) -> int:
    return max(0, math.ceil((minutes or 0) / 60))

def price_quote(inp: Dict[str, Any], data: Dict[str, Any], policies: Dict[str, Any]) -> Dict[str, Any]:
    g = int(inp.get("guests", 0))
    duration_hr = _ceil_hours(int(inp.get("duration_minutes", 0)))
    open_bar_hours = _ceil_hours(int(inp.get("open_bar_duration_minutes", 0))) if inp.get("open_bar_tier_id") else 0
    line_items: List[List[Any]] = []

    food_total = 0.0
    if inp.get("package_type") == "food_package" and inp.get("food_package_id"):
        pkg = data["packages_food"][inp["food_package_id"]]
        unit = float(pkg["price_pp"]); total = g * unit
        line_items.append([f"Food Package: {pkg['name']}", g, unit, total]); food_total += total
        for extra_id in inp.get("food_extras", []):
            extra = data["food_extras_lookup"][extra_id]
            price_map = {
                "starter": float(pkg.get("extras_price_pp_starter", 0)),
                "main": float(pkg.get("extras_price_pp_main", 0)),
                "dessert": float(pkg.get("extras_price_pp_dessert", 0)),
                "special": float(pkg.get("extras_price_pp_special", 0)),
            }
            unit_extra = price_map[extra["type"]]; total_extra = g * unit_extra
            line_items.append([f"Extra: {extra['name']}", g, unit_extra, total_extra]); food_total += total_extra
    elif inp.get("package_type") == "food_experience" and inp.get("experience_id"):
        exp = data["experiences_food"][inp["experience_id"]]
        unit = float(exp["price_pp"]); total = g * unit
        line_items.append([f"Food Experience: {exp['name']}", g, unit, total]); food_total += total

    alcohol_total = 0.0
    if inp.get("happy_hour_tier_id"):
        hh = data["happy_hour_packages"][inp["happy_hour_tier_id"]]
        unit = float(hh["price_pp_2hr"]); total = g * unit
        line_items.append([f"Happy Hour: {hh['tier_name']} (2hr)", g, unit, total]); alcohol_total += total
        extra_choices = int(inp.get("happy_hour_extra_choices", 0) or 0)
        if extra_choices > 0:
            extra_unit = float(hh.get("extra_choice_price_pp", 0)) * extra_choices
            extra_total = g * extra_unit
            line_items.append(["Happy Hour extra selections", g, extra_unit, extra_total]); alcohol_total += extra_total

    if inp.get("open_bar_tier_id") and open_bar_hours > 0:
        tier = data["beverages_open_bar"][inp["open_bar_tier_id"]]
        base_unit = float(tier["base_price_pp_2hr"]); base_total = g * base_unit
        line_items.append([f"Open Bar: {tier['tier_name']} (first 2hr)", g, base_unit, base_total]); alcohol_total += base_total
        if open_bar_hours > 2:
            addl_hours = open_bar_hours - 2; addl_unit = float(tier["addl_hour_price_pp"]); addl_total = g * addl_hours * addl_unit
            line_items.append([f"Open Bar: {tier['tier_name']} (additional {addl_hours} hr)", g, addl_unit, addl_total]); alcohol_total += addl_total

    tickets = inp.get("drink_tickets") or {}
    if tickets and int(tickets.get("tickets_per_guest", 0)) > 0:
        t = data["beverages_open_bar"][tickets["tier_id"]]
        unit = float(t["ticket_price"]); total = g * int(tickets["tickets_per_guest"]) * unit
        line_items.append([f"Drink Tickets: {t['tier_name']} x{tickets['tickets_per_guest']}/guest", g, unit, total]); alcohol_total += total

    if inp.get("late_night_tier_id"):
        ln = data["late_night_open_bar"][inp["late_night_tier_id"]]
        unit = float(ln["price_pp_2hr"]); total = g * unit
        line_items.append([f"Late-Night Open Bar: {ln['tier_name']} (2hr, beverages only)", g, unit, total]); alcohol_total += total

    rental_total = 0.0
    if not inp.get("waive_private_rental") and g > int(policies["private_rental_threshold_guests"]):
        rate = float(policies["private_rental_weekday_rate_per_hour"]) if inp.get("day_type") == "weekday" else float(policies["private_rental_weekend_rate_per_hour"])
        rental_total = rate * duration_hr
        line_items.append([f"Private Rental ({inp.get('day_type','')})", duration_hr, rate, rental_total])

    has_alcohol = any([inp.get("open_bar_tier_id"), (tickets and int(tickets.get("tickets_per_guest", 0)) > 0), inp.get("happy_hour_tier_id"), inp.get("late_night_tier_id")])
    bartender_total = 0.0
    if g > int(policies["second_bartender_threshold_guests"]):
        mode = policies.get("second_bartender_applies_when", "any_alcohol_service")
        applies = (mode == "always") or (mode == "any_alcohol_service" and has_alcohol) or (mode == "open_bar_only" and inp.get("open_bar_tier_id"))
        if applies:
            if inp.get("open_bar_tier_id") and inp.get("open_bar_duration_minutes"): service_hours = open_bar_hours
            elif inp.get("happy_hour_tier_id"): service_hours = 2
            elif inp.get("late_night_tier_id"): service_hours = 2
            else: service_hours = duration_hr
            rate = float(policies["second_bartender_rate_per_hour"]); bartender_total = service_hours * rate
            line_items.append([f"Second Bartender (> {policies['second_bartender_threshold_guests']} guests)", service_hours, rate, bartender_total])

    subtotal = food_total + alcohol_total + rental_total + bartender_total
    gratuity = subtotal * float(policies["gratuity_rate"])
    alloc = (lambda base: (gratuity * (base / subtotal))) if subtotal > 0 else (lambda base: 0.0)

    food_tax_base = food_total + alloc(food_total)
    alcohol_tax_base = alcohol_total + alloc(alcohol_total)

    food_tax = food_tax_base * float(policies["tax_food_rate"])
    alcohol_tax = alcohol_tax_base * float(policies["tax_alcohol_rate"])

    staff_tax = 0.0
    tax_total = food_tax + alcohol_tax + staff_tax
    grand_total = subtotal + gratuity + tax_total

    def _round(x): return round(float(x), 2)
    return {
        "line_items": [{"label": li[0], "quantity": li[1], "unit_price": _round(li[2]), "total": _round(li[3])} for li in line_items],
        "category_subtotals": {"food": _round(food_total), "alcohol": _round(alcohol_total), "rental": _round(rental_total), "staff": _round(bartender_total)},
        "subtotal": _round(subtotal), "gratuity": _round(gratuity),
        "food_tax": _round(food_tax), "alcohol_tax": _round(alcohol_tax),
        "staff_tax": _round(staff_tax), "tax_total": _round(tax_total), "grand_total": _round(grand_total),
        "disclosures": policies.get("disclosures", []),
    }
