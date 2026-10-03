/* Booking popup: date -> time slot -> plan -> guests. Plain JS, no framework dependency. */
(function () {
    "use strict";

    function money(value, currency) {
        try {
            return new Intl.NumberFormat(undefined, {style: "currency", currency: currency}).format(value);
        } catch (e) {
            return value.toFixed(2) + " " + currency;
        }
    }

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        if (text !== undefined) {
            node.textContent = text;
        }
        return node;
    }

    function setup(modal) {
        var form = modal.querySelector("form");
        var productId = form.dataset.product;
        var currency = form.dataset.currency;
        var dateBox = modal.querySelector(".o_bk_dates");
        var slotBox = modal.querySelector(".o_bk_slots");
        var planBox = modal.querySelector(".o_bk_plans");
        var minusBtn = modal.querySelector(".o_bk_minus");
        var plusBtn = modal.querySelector(".o_bk_plus");
        var qtyLabel = modal.querySelector(".o_bk_qty_value");
        var hint = modal.querySelector(".o_bk_hint");
        var totalEl = modal.querySelector(".o_bk_total");
        var submitBtn = modal.querySelector(".o_bk_submit");
        var inDate = form.querySelector("input[name=date]");
        var inSlot = form.querySelector("input[name=slot_id]");
        var inPlan = form.querySelector("input[name=plan_id]");
        var inQty = form.querySelector("input[name=qty]");
        var state = {date: null, slot: null, plan: null, qty: 1, slots: [], loading: false, token: 0};

        // ---- calendar: built from the date chips, so it follows the same rules ----
        // (closed weekdays, closing periods, start / end date and advance limit)
        var calBox = modal.querySelector(".o_bk_cal");
        var calToggle = modal.querySelector(".o_bk_cal_toggle");
        var dayMap = {};
        var keys = [];
        var cal = {year: null, month: null};
        Array.prototype.forEach.call(dateBox.querySelectorAll(".o_bk_date"), function (chip) {
            dayMap[chip.dataset.date] = chip;
            keys.push(chip.dataset.date);
        });
        keys.sort();

        function pad(n) {
            return (n < 10 ? "0" : "") + n;
        }

        function dayKey(y, m, d) {
            return y + "-" + pad(m + 1) + "-" + pad(d);
        }

        function parseKey(k) {
            var p = k.split("-");
            return {y: parseInt(p[0], 10), m: parseInt(p[1], 10) - 1, d: parseInt(p[2], 10)};
        }

        function format(date, options) {
            var lang = document.documentElement.lang || undefined;
            try {
                return new Intl.DateTimeFormat(lang, options).format(date);
            } catch (e) {
                return new Intl.DateTimeFormat(undefined, options).format(date);
            }
        }

        function centerChip(chip) {
            dateBox.scrollTo({
                left: chip.offsetLeft - (dateBox.clientWidth - chip.offsetWidth) / 2,
                behavior: "smooth",
            });
        }

        function hideCalendar() {
            calBox.classList.add("d-none");
            calToggle.classList.remove("active");
        }

        function bindDay(cell, k) {
            cell.addEventListener("click", function () {
                var chip = dayMap[k];
                selectDate(chip);
                centerChip(chip);
                hideCalendar();
            });
        }

        function shiftMonth(step) {
            var idx = cal.year * 12 + cal.month + step;
            cal.year = Math.floor(idx / 12);
            cal.month = idx % 12;
            renderCalendar();
        }

        function renderCalendar() {
            calBox.textContent = "";
            if (!keys.length || cal.year === null) {
                return;
            }
            var firstP = parseKey(keys[0]);
            var lastP = parseKey(keys[keys.length - 1]);
            var idx = cal.year * 12 + cal.month;

            var head = el("div", "o_bk_cal_head");
            var prev = el("button", "o_bk_arrow", "\u2039");
            prev.type = "button";
            prev.disabled = idx <= firstP.y * 12 + firstP.m;
            prev.addEventListener("click", function () { shiftMonth(-1); });
            var next = el("button", "o_bk_arrow", "\u203a");
            next.type = "button";
            next.disabled = idx >= lastP.y * 12 + lastP.m;
            next.addEventListener("click", function () { shiftMonth(1); });
            head.appendChild(prev);
            head.appendChild(el("div", "o_bk_cal_title",
                format(new Date(cal.year, cal.month, 1), {month: "long", year: "numeric"})));
            head.appendChild(next);

            var grid = el("div", "o_bk_cal_grid");
            for (var i = 0; i < 7; i++) {
                // 2024-01-01 is a Monday: the calendar starts on Monday
                grid.appendChild(el("div", "o_bk_cal_wd",
                    format(new Date(2024, 0, 1 + i), {weekday: "short"})));
            }
            var offset = (new Date(cal.year, cal.month, 1).getDay() + 6) % 7;
            for (var b = 0; b < offset; b++) {
                grid.appendChild(el("div", "o_bk_cal_blank"));
            }
            var daysInMonth = new Date(cal.year, cal.month + 1, 0).getDate();
            for (var d = 1; d <= daysInMonth; d++) {
                var k = dayKey(cal.year, cal.month, d);
                var chip = dayMap[k];
                var enabled = !!chip && !chip.disabled;
                var cell = el("button",
                    "o_bk_cal_day" + (enabled ? "" : " off") + (k === state.date ? " active" : ""),
                    String(d));
                cell.type = "button";
                cell.disabled = !enabled;
                if (!enabled) {
                    cell.title = chip ? "Closed" : "Not available";
                } else {
                    bindDay(cell, k);
                }
                grid.appendChild(cell);
            }
            calBox.appendChild(head);
            calBox.appendChild(grid);
        }

        function currentSlot() {
            return state.slots.find(function (s) { return s.id === state.slot; }) || null;
        }

        function currentPlan() {
            var slot = currentSlot();
            if (!slot) {
                return null;
            }
            return slot.plans.find(function (p) { return p.id === state.plan; }) || null;
        }

        function renderSlots() {
            slotBox.textContent = "";
            if (!state.date) {
                slotBox.appendChild(el("div", "o_bk_empty", "Select a date first."));
                return;
            }
            if (state.loading) {
                slotBox.appendChild(el("div", "o_bk_empty", "Loading..."));
                return;
            }
            if (!state.slots.length) {
                slotBox.appendChild(el("div", "o_bk_empty", "No time slot available on this date."));
                return;
            }
            state.slots.forEach(function (slot) {
                var soldOut = slot.plans.every(function (p) { return p.left < 1; });
                var btn = el("button", "o_bk_slot" + (slot.id === state.slot ? " active" : ""), slot.name);
                btn.type = "button";
                btn.disabled = soldOut;
                if (soldOut) {
                    btn.title = "Sold out";
                }
                btn.addEventListener("click", function () {
                    state.slot = slot.id;
                    autoPickPlan();
                    render();
                });
                slotBox.appendChild(btn);
            });
        }

        function renderPlans() {
            planBox.textContent = "";
            var slot = currentSlot();
            if (!slot) {
                planBox.appendChild(el("div", "o_bk_empty", "Select a time first."));
                return;
            }
            slot.plans.forEach(function (plan) {
                var soldOut = plan.left < 1;
                var card = el("button", "o_bk_plan" + (plan.id === state.plan ? " active" : ""));
                card.type = "button";
                card.disabled = soldOut;
                var info = el("span", "o_bk_plan_info");
                info.appendChild(el("span", "o_bk_plan_name", plan.name));
                if (plan.description) {
                    info.appendChild(el("span", "o_bk_plan_desc", plan.description));
                }
                var side = el("span", "o_bk_plan_side");
                side.appendChild(el("span", "o_bk_plan_price", money(plan.price, currency)));
                side.appendChild(el("span", "o_bk_plan_left" + (soldOut ? " sold" : ""),
                    soldOut ? "Sold out" : plan.left + " left"));
                card.appendChild(info);
                card.appendChild(side);
                card.addEventListener("click", function () {
                    state.plan = plan.id;
                    render();
                });
                planBox.appendChild(card);
            });
        }

        function renderSummary() {
            var plan = currentPlan();
            var max = plan ? plan.left : 0;
            if (state.qty > max) {
                state.qty = max;
            }
            if (state.qty < 1) {
                state.qty = 1;
            }
            qtyLabel.textContent = state.qty;
            minusBtn.disabled = state.qty <= 1;
            plusBtn.disabled = !plan || state.qty >= max;
            hint.textContent = plan ? "Up to " + max + " available" : "Choose a date, time and plan";
            totalEl.textContent = plan ? money(plan.price * state.qty, currency) : "-";
            inDate.value = state.date || "";
            inSlot.value = state.slot || "";
            inPlan.value = state.plan || "";
            inQty.value = state.qty;
            submitBtn.disabled = !(state.date && state.slot && plan && max >= 1);
        }

        function render() {
            renderSlots();
            renderPlans();
            renderSummary();
        }

        // Keep the chosen plan when it is still available in the slot, else take the first open one.
        function autoPickPlan() {
            var slot = currentSlot();
            if (!slot) {
                return;
            }
            var current = currentPlan();
            if (current && current.left > 0) {
                return;
            }
            var open = slot.plans.filter(function (p) { return p.left > 0; });
            state.plan = open.length ? open[0].id : null;
        }

        // After loading a date: select the first available time slot and its first available plan.
        function autoPickSlot() {
            var open = state.slots.filter(function (s) {
                return s.plans.some(function (p) { return p.left > 0; });
            });
            if (!open.length) {
                return;
            }
            state.slot = open[0].id;
            autoPickPlan();
        }

        function selectDate(btn) {
            state.date = btn.dataset.date;
            state.slot = null;
            state.plan = null;
            state.qty = 1;
            state.slots = [];
            state.loading = true;
            Array.prototype.forEach.call(dateBox.querySelectorAll(".o_bk_date"), function (b) {
                b.classList.toggle("active", b === btn);
            });
            var picked = parseKey(state.date);
            cal.year = picked.y;
            cal.month = picked.m;
            renderCalendar();
            render();
            var token = ++state.token;
            var params = new URLSearchParams({product_tmpl_id: productId, date: state.date});
            fetch("/booking/availability?" + params.toString(), {
                headers: {Accept: "application/json"},
                credentials: "same-origin",
            }).then(function (response) {
                return response.ok ? response.json() : {slots: []};
            }).then(function (data) {
                if (token !== state.token) {
                    return;
                }
                state.slots = data.slots || [];
                state.loading = false;
                autoPickSlot();
                render();
            }).catch(function () {
                if (token !== state.token) {
                    return;
                }
                state.slots = [];
                state.loading = false;
                render();
            });
        }

        dateBox.addEventListener("click", function (ev) {
            var btn = ev.target.closest(".o_bk_date");
            if (btn && !btn.disabled) {
                selectDate(btn);
            }
        });
        modal.querySelector(".o_bk_prev").addEventListener("click", function () {
            dateBox.scrollBy({left: -dateBox.clientWidth * 0.8, behavior: "smooth"});
        });
        modal.querySelector(".o_bk_next").addEventListener("click", function () {
            dateBox.scrollBy({left: dateBox.clientWidth * 0.8, behavior: "smooth"});
        });
        calToggle.addEventListener("click", function () {
            var hidden = calBox.classList.toggle("d-none");
            calToggle.classList.toggle("active", !hidden);
            if (!hidden) {
                renderCalendar();
            }
        });
        minusBtn.addEventListener("click", function () {
            state.qty -= 1;
            renderSummary();
        });
        plusBtn.addEventListener("click", function () {
            state.qty += 1;
            renderSummary();
        });
        form.addEventListener("submit", function (ev) {
            if (submitBtn.disabled) {
                ev.preventDefault();
            }
        });

        // Use the exact colour of the theme's primary button for the selected states.
        var probe = document.querySelector('[data-bs-target="#' + modal.id + '"]') || submitBtn;
        var accent = window.getComputedStyle(probe).backgroundColor;
        if (accent && accent !== "transparent" && accent !== "rgba(0, 0, 0, 0)") {
            modal.style.setProperty("--bk-accent", accent);
        }

        render();
        var first = dateBox.querySelector(".o_bk_date:not([disabled])");
        if (first) {
            selectDate(first);
            centerChip(first);
        }
    }

    function init() {
        Array.prototype.forEach.call(document.querySelectorAll(".o_booking_modal"), setup);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
