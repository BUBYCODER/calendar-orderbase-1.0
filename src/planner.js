export function safeParseDate(dVal) {
  if (!dVal) return null;
  try {
    const s = String(dVal).trim().slice(0, 10);
    const parts = s.split('-').map(Number);
    if (parts.length === 3 && !isNaN(parts[0]) && !isNaN(parts[1]) && !isNaN(parts[2])) {
      return { year: parts[0], month: parts[1], day: parts[2], iso: s };
    }
  } catch {}
  return null;
}

export function toOrdinal(y, m, d) {
  const msPerDay = 86400000;
  return Math.floor(Date.UTC(y, m - 1, d) / msPerDay) + 719163;
}

export function fromOrdinal(ord) {
  const ms = (ord - 719163) * 86400000;
  const d = new Date(ms);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return { iso: `${y}-${m}-${day}`, year: y, month: d.getUTCMonth() + 1, day: d.getUTCDate() };
}

export function dateToAbsQ(dStr, q) {
  const parsed = safeParseDate(dStr);
  if (!parsed) return 0;
  const qInt = Math.max(1, Math.min(4, parseInt(q, 10) || 1));
  const ord = toOrdinal(parsed.year, parsed.month, parsed.day);
  return ord * 4 + qInt - 1;
}

export function absToDateAndQ(absQ) {
  try {
    const ord = Math.floor(Number(absQ) / 4);
    const q = (Number(absQ) % 4) + 1;
    const d = fromOrdinal(ord);
    return [d.iso, q];
  } catch {
    const today = new Date().toISOString().slice(0, 10);
    return [today, 1];
  }
}

export function touchesMonth(order, year, month) {
  const startD = safeParseDate(order.start_date);
  const endD = safeParseDate(order.end_date);
  if (!startD || !endD) return false;
  try {
    const mStartOrd = toOrdinal(year, month, 1);
    const lastDayOfMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
    const mEndOrd = toOrdinal(year, month, lastDayOfMonth);
    const startOrd = toOrdinal(startD.year, startD.month, startD.day);
    const endOrd = toOrdinal(endD.year, endD.month, endD.day);
    return !(endOrd < mStartOrd || startOrd > mEndOrd);
  } catch {
    return false;
  }
}

export function calculateOrderPiecesForMonth(quantity, startDateStr, startQ, endDateStr, endQ, targetYear, targetMonth) {
  if (!quantity || quantity <= 0 || !startDateStr || !endDateStr) return 0;

  const sAbs = dateToAbsQ(startDateStr, startQ);
  const eAbs = dateToAbsQ(endDateStr, endQ);
  const totalQ = eAbs - sAbs + 1;
  if (totalQ <= 0) return 0;

  const sDate = fromOrdinal(Math.floor(sAbs / 4));
  const eDate = fromOrdinal(Math.floor(eAbs / 4));

  const months = [];
  let currY = sDate.year;
  let currM = sDate.month;
  const endY = eDate.year;
  const endM = eDate.month;

  while (currY < endY || (currY === endY && currM <= endM)) {
    months.push([currY, currM]);
    if (currM === 12) {
      currY += 1;
      currM = 1;
    } else {
      currM += 1;
    }
  }

  if (months.length === 1) {
    return (targetYear === months[0][0] && targetMonth === months[0][1]) ? quantity : 0;
  }

  const monthDurations = [];
  for (let idx = 0; idx < months.length; idx++) {
    const [y, m] = months[idx];
    const lastDay = new Date(Date.UTC(y, m, 0)).getUTCDate();
    const mStartAbs = toOrdinal(y, m, 1) * 4;
    const mEndAbs = toOrdinal(y, m, lastDay) * 4 + 3;

    const overlapStart = Math.max(sAbs, mStartAbs);
    const overlapEnd = Math.min(eAbs, mEndAbs);
    const dur = Math.max(0, overlapEnd - overlapStart + 1);
    monthDurations.push({ year: y, month: m, dur, idx });
  }

  const allocated = new Map();
  const remainders = [];
  let baseSum = 0;
  for (const item of monthDurations) {
    const dur = item.dur;
    const exact = (quantity * dur) / totalQ;
    const base = Math.floor(exact);
    allocated.set(`${item.year}-${item.month}`, base);
    baseSum += base;
    remainders.push({ dur, idx: item.idx, year: item.year, month: item.month });
  }

  const leftover = quantity - baseSum;
  remainders.sort((a, b) => {
    if (b.dur !== a.dur) return b.dur - a.dur;
    return b.idx - a.idx;
  });

  for (let i = 0; i < leftover; i++) {
    const item = remainders[i];
    const key = `${item.year}-${item.month}`;
    allocated.set(key, (allocated.get(key) || 0) + 1);
  }

  return allocated.get(`${targetYear}-${targetMonth}`) || 0;
}

export function getMonthCalendar(year, month, mainOrders, otherOrders) {
  const firstDay = new Date(Date.UTC(year, month - 1, 1));
  const startDayOfWeek = (firstDay.getUTCDay() + 6) % 7; // Monday = 0
  const startDate = new Date(Date.UTC(year, month - 1, 1 - startDayOfWeek));

  const lastDay = new Date(Date.UTC(year, month, 0));
  const endDayOfWeek = (lastDay.getUTCDay() + 6) % 7;
  const endDate = new Date(Date.UTC(year, month - 1, lastDay.getUTCDate() + (6 - endDayOfWeek)));

  const result = [];
  const todayIso = new Date().toISOString().slice(0, 10);

  for (let i = 0; i < mainOrders.length; i++) {
    mainOrders[i].day_bg_class = `day-bg-${i % 6}`;
  }

  let curr = new Date(startDate.getTime());
  while (curr <= endDate) {
    const y = curr.getUTCFullYear();
    const m = curr.getUTCMonth() + 1;
    const d = curr.getUTCDate();
    const dateStr = `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const dayAbsQStart = toOrdinal(y, m, d) * 4;

    const dayQuarters = [null, null, null, null];
    const crossIndicators = [false, false, false, false];

    let startOrderName = null;
    let startOrderId = null;
    let startOrderBadgeText = null;

    for (const order of mainOrders) {
      if (order.start_date === dateStr) {
        const num = order.order_number || order.id;
        startOrderName = order.name;
        startOrderId = order.id;
        startOrderBadgeText = `#${num}`;
        break;
      }
    }

    for (const order of otherOrders) {
      if (order.order_type === 'sample') {
        const sAbsQ = dateToAbsQ(order.start_date, order.start_q);
        const eAbsQ = dateToAbsQ(order.end_date, order.end_q);
        if (sAbsQ <= dayAbsQStart + 3 && eAbsQ >= dayAbsQStart) {
          const qStart = Math.max(0, sAbsQ - dayAbsQStart);
          const qEnd = Math.min(3, eAbsQ - dayAbsQStart);
          for (let idx = qStart; idx <= qEnd; idx++) {
            crossIndicators[idx] = true;
          }
        }
      } else {
        for (const stage of order.stages || []) {
          const sAbsQ = dateToAbsQ(stage.start, stage.start_q);
          const eAbsQ = dateToAbsQ(stage.end, stage.end_q);
          if (sAbsQ <= dayAbsQStart + 3 && eAbsQ >= dayAbsQStart) {
            const qStart = Math.max(0, sAbsQ - dayAbsQStart);
            const qEnd = Math.min(3, eAbsQ - dayAbsQStart);
            for (let idx = qStart; idx <= qEnd; idx++) {
              crossIndicators[idx] = true;
            }
          }
        }
      }
    }

    for (let orderIdx = 0; orderIdx < mainOrders.length; orderIdx++) {
      const order = mainOrders[orderIdx];
      const num = order.order_number || order.id;
      const qty = order.quantity || 0;
      const orderLabel = `#${num}`;

      if (order.order_type === 'sample') {
        const sAbsQ = dateToAbsQ(order.start_date, order.start_q);
        const eAbsQ = dateToAbsQ(order.end_date, order.end_q);

        if (sAbsQ <= dayAbsQStart + 3 && eAbsQ >= dayAbsQStart) {
          const qStartIdx = Math.max(0, sAbsQ - dayAbsQStart);
          const qEndIdx = Math.min(3, eAbsQ - dayAbsQStart);
          const cssClass = `order-bg-${orderIdx % 6} order-border-${orderIdx % 6}`;

          for (let idx = qStartIdx; idx <= qEndIdx; idx++) {
            dayQuarters[idx] = {
              order_id: order.id,
              order_name: order.name,
              order_number: num,
              quantity: qty,
              stage_type: orderLabel,
              css_class: cssClass,
              day_bg_class: order.day_bg_class
            };
          }
        }
      } else {
        for (const stage of order.stages || []) {
          const sAbsQ = dateToAbsQ(stage.start, stage.start_q);
          const eAbsQ = dateToAbsQ(stage.end, stage.end_q);

          if (sAbsQ <= dayAbsQStart + 3 && eAbsQ >= dayAbsQStart) {
            const qStartIdx = Math.max(0, sAbsQ - dayAbsQStart);
            const qEndIdx = Math.min(3, eAbsQ - dayAbsQStart);

            const slug = (stage.type || '').toLowerCase().replace(/\s+/g, '-').replace(/[()]/g, '');
            const cssClass = `stage-bg-${slug} order-border-${orderIdx % 6}`;

            for (let idx = qStartIdx; idx <= qEndIdx; idx++) {
              dayQuarters[idx] = {
                order_id: order.id,
                order_name: order.name,
                order_number: num,
                quantity: qty,
                stage_type: stage.type,
                cell_display: `#${num} ${stage.type}`,
                css_class: cssClass,
                day_bg_class: order.day_bg_class
              };
            }
          }
        }
      }
    }

    const processedQuarters = [];
    let dayBgClass = 'day-bg-none';

    const orderCounts = {};
    for (const q of dayQuarters) {
      if (q) orderCounts[q.order_id] = (orderCounts[q.order_id] || 0) + 1;
    }

    const distinctOrderIds = Object.keys(orderCounts);
    if (distinctOrderIds.length === 1) {
      const dominantOrderId = Number(distinctOrderIds[0]);
      for (const q of dayQuarters) {
        if (q && q.order_id === dominantOrderId) {
          dayBgClass = q.day_bg_class;
          break;
        }
      }
    } else {
      dayBgClass = 'day-bg-none';
    }

    for (let i = 0; i < 4; i++) {
      const q = dayQuarters[i];
      if (!q) {
        processedQuarters.push({ is_empty: true });
      } else {
        let connR = false, connB = false, connL = false, connT = false;
        if (i === 0) {
          if (dayQuarters[1] && dayQuarters[1].order_id === q.order_id && dayQuarters[1].stage_type === q.stage_type) connR = true;
          if (dayQuarters[2] && dayQuarters[2].order_id === q.order_id && dayQuarters[2].stage_type === q.stage_type) connB = true;
        } else if (i === 1) {
          if (dayQuarters[0] && dayQuarters[0].order_id === q.order_id && dayQuarters[0].stage_type === q.stage_type) connL = true;
          if (dayQuarters[3] && dayQuarters[3].order_id === q.order_id && dayQuarters[3].stage_type === q.stage_type) connB = true;
        } else if (i === 2) {
          if (dayQuarters[0] && dayQuarters[0].order_id === q.order_id && dayQuarters[0].stage_type === q.stage_type) connT = true;
          if (dayQuarters[3] && dayQuarters[3].order_id === q.order_id && dayQuarters[3].stage_type === q.stage_type) connR = true;
        } else if (i === 3) {
          if (dayQuarters[2] && dayQuarters[2].order_id === q.order_id && dayQuarters[2].stage_type === q.stage_type) connL = true;
          if (dayQuarters[1] && dayQuarters[1].order_id === q.order_id && dayQuarters[1].stage_type === q.stage_type) connT = true;
        }

        let showText = false;
        if (i === 0) showText = true;
        else if (i === 1 && !connL) showText = true;
        else if (i === 2 && !connT && !(dayQuarters[1] && dayQuarters[1].order_id === q.order_id && dayQuarters[1].stage_type === q.stage_type)) showText = true;
        else if (i === 3 && !connL && !connT && !(dayQuarters[0] && dayQuarters[0].order_id === q.order_id && dayQuarters[0].stage_type === q.stage_type)) showText = true;

        processedQuarters.push({
          is_empty: false,
          css_class: q.css_class,
          stage_type: q.stage_type,
          cell_display: q.cell_display || q.stage_type,
          order_name: q.order_name,
          order_id: q.order_id,
          order_number: q.order_number,
          quantity: q.quantity,
          conn_r: connR,
          conn_b: connB,
          conn_l: connL,
          conn_t: connT,
          show_text: showText
        });
      }
    }

    result.push({
      date: new Date(curr.getTime()),
      date_str: dateStr,
      day: d,
      quarters: processedQuarters,
      cross_indicators: crossIndicators,
      is_other_month: m !== month,
      is_today: dateStr === todayIso,
      day_bg_class: dayBgClass,
      start_order_name: startOrderName,
      start_order_id: startOrderId,
      start_order_badge_text: startOrderBadgeText
    });

    curr.setUTCDate(curr.getUTCDate() + 1);
  }

  return result;
}

export function getMonthName(month) {
  return ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'][month] || '';
}
