"use strict";

const API_URL = "/api/v1/tickets";
const PAGE_SIZE = 8;
const TOAST_DURATION_MS = 3500;
const AUTO_REFRESH_MS = 30000;
const HEALTH_CHECK_MS = 15000;

const STATUS_LABELS = {
    new: "Новая",
    in_progress: "В работе",
    closed: "Закрыта",
};

const STATUS_COLORS = {
    new: "var(--new)",
    in_progress: "var(--in-progress)",
    closed: "var(--closed)",
};

const PRIORITY_LABELS = {
    low: "Низкий",
    medium: "Средний",
    high: "Высокий",
    critical: "Критический",
};

const PRIORITY_LEVELS = { low: 1, medium: 2, high: 3, critical: 4 };

const SEARCH_DEBOUNCE_MS = 300;

const state = {
    status: "",
    search: "",
    sort: "newest",
    offset: 0,
    total: 0,
    selectedId: null,
};

const byId = (id) => document.getElementById(id);

const el = {
    apiStatus: byId("api-status"),
    stats: byId("stats"),
    tabs: byId("status-tabs"),
    search: byId("search"),
    sort: byId("sort"),
    list: byId("ticket-list"),
    emptyState: byId("empty-state"),
    pageInfo: byId("page-info"),
    prevPage: byId("prev-page"),
    nextPage: byId("next-page"),
    refresh: byId("refresh"),
    overlay: byId("overlay"),
    drawer: byId("drawer"),
    drawerId: byId("drawer-id"),
    drawerTitle: byId("drawer-title"),
    drawerBadges: byId("drawer-badges"),
    drawerEmail: byId("drawer-email"),
    drawerCreated: byId("drawer-created"),
    drawerUpdated: byId("drawer-updated"),
    drawerDescription: byId("drawer-description"),
    drawerActions: byId("drawer-actions"),
    drawerTimeline: byId("drawer-timeline"),
    deleteButton: byId("delete-ticket"),
    modal: byId("modal"),
    form: byId("ticket-form"),
    formError: byId("form-error"),
    openCreate: byId("open-create"),
    toasts: byId("toasts"),
};

/* ---------- Helpers ---------- */

function h(tag, className = "", text = undefined) {
    const node = document.createElement(tag);
    if (className) {
        node.className = className;
    }
    if (text !== undefined) {
        node.textContent = text;
    }
    return node;
}

async function request(path, options = {}) {
    const response = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(formatApiError(body.detail) || response.statusText);
    }
    return response.status === 204 ? null : response.json();
}

function formatApiError(detail) {
    if (Array.isArray(detail)) {
        return detail.map((item) => `${item.loc.at(-1)}: ${item.msg}`).join("; ");
    }
    return detail;
}

const relativeFormatter = new Intl.RelativeTimeFormat("ru", { numeric: "auto" });
const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
});

const TIME_UNITS = [
    ["year", 31536000],
    ["month", 2592000],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
];

function formatRelative(isoDate) {
    const seconds = Math.round((new Date(isoDate) - Date.now()) / 1000);
    for (const [unit, size] of TIME_UNITS) {
        if (Math.abs(seconds) >= size) {
            return relativeFormatter.format(Math.round(seconds / size), unit);
        }
    }
    return "только что";
}

function formatDate(isoDate) {
    return dateFormatter.format(new Date(isoDate));
}

function animateNumber(node, target) {
    const start = Number(node.textContent) || 0;
    if (start === target) {
        node.textContent = target;
        return;
    }
    const startedAt = performance.now();
    const duration = 500;
    const step = (now) => {
        const progress = Math.min(1, (now - startedAt) / duration);
        const eased = 1 - (1 - progress) ** 3;
        node.textContent = Math.round(start + (target - start) * eased);
        if (progress < 1) {
            requestAnimationFrame(step);
        }
    };
    requestAnimationFrame(step);
}

/* ---------- Components ---------- */

function highlight(text) {
    const fragment = document.createDocumentFragment();
    const query = state.search.toLowerCase();
    if (!query) {
        fragment.append(text);
        return fragment;
    }
    const lowerText = text.toLowerCase();
    let position = 0;
    let index = lowerText.indexOf(query);
    while (index !== -1) {
        fragment.append(
            text.slice(position, index),
            h("mark", "", text.slice(index, index + query.length)),
        );
        position = index + query.length;
        index = lowerText.indexOf(query, position);
    }
    fragment.append(text.slice(position));
    return fragment;
}

function statusBadge(status) {
    return h("span", `badge badge--${status}`, STATUS_LABELS[status]);
}

function priorityIndicator(priority) {
    const wrapper = h("span", `priority priority--${priority}`);
    const bars = h("span", "priority__bars");
    for (let level = 1; level <= 4; level += 1) {
        bars.append(h("i", level <= PRIORITY_LEVELS[priority] ? "is-on" : ""));
    }
    wrapper.append(bars, h("span", "", PRIORITY_LABELS[priority]));
    return wrapper;
}

function actionLabel(current, target) {
    if (target === "in_progress") {
        return current === "closed" ? "Переоткрыть" : "Взять в работу";
    }
    if (target === "closed") {
        return "Закрыть заявку";
    }
    return "Вернуть в очередь";
}

function toast(message, type = "success") {
    const node = h("div", `toast toast--${type}`, message);
    el.toasts.append(node);
    setTimeout(() => {
        node.classList.add("is-leaving");
        node.addEventListener("transitionend", () => node.remove(), { once: true });
    }, TOAST_DURATION_MS);
}

/* ---------- Ticket list ---------- */

function renderSkeleton() {
    const rows = Array.from({ length: 4 }, () => {
        const li = h("li", "ticket");
        const main = h("div", "ticket__main");
        const title = h("div", "skeleton");
        title.style.width = "55%";
        const sub = h("div", "skeleton");
        sub.style.cssText = "width: 35%; margin-top: 8px; height: 10px";
        main.append(title, sub);
        li.append(main, h("div", "skeleton"), h("div", "skeleton"), h("div", "skeleton"));
        return li;
    });
    el.list.replaceChildren(...rows);
    el.emptyState.hidden = true;
}

function renderTickets(tickets) {
    const rows = tickets.map((ticket, index) => {
        const li = h("li", "ticket");
        li.dataset.id = ticket.id;
        li.style.animationDelay = `${index * 30}ms`;
        li.classList.toggle("is-selected", ticket.id === state.selectedId);

        const main = h("div", "ticket__main");
        const title = h("div", "ticket__title");
        title.append(h("span", "ticket__id", `#${ticket.id}`), highlight(ticket.title));
        const sub = h("div", "ticket__sub", `${ticket.customer_email} · `);
        sub.append(highlight(ticket.description));
        main.append(title, sub);

        const statusCell = h("div");
        statusCell.append(statusBadge(ticket.status));

        const time = h("span", "ticket__time", formatRelative(ticket.created_at));
        time.title = formatDate(ticket.created_at);

        li.append(main, priorityIndicator(ticket.priority), statusCell, time);
        return li;
    });
    el.list.replaceChildren(...rows);
    el.emptyState.hidden = tickets.length > 0;
    el.emptyState.querySelector(".empty__title").textContent = state.search
        ? `По запросу «${state.search}» ничего не найдено`
        : "Заявок нет";
}

function renderPagination() {
    if (state.total === 0) {
        el.pageInfo.textContent = "Нет заявок";
    } else {
        const from = state.offset + 1;
        const to = Math.min(state.offset + PAGE_SIZE, state.total);
        el.pageInfo.textContent = `Показано ${from}–${to} из ${state.total}`;
    }
    el.prevPage.disabled = state.offset === 0;
    el.nextPage.disabled = state.offset + PAGE_SIZE >= state.total;
}

function highlightSelected() {
    for (const row of el.list.querySelectorAll(".ticket")) {
        row.classList.toggle("is-selected", Number(row.dataset.id) === state.selectedId);
    }
}

async function loadTickets({ silent = false } = {}) {
    if (!silent) {
        renderSkeleton();
    }
    const params = new URLSearchParams({
        limit: PAGE_SIZE,
        offset: state.offset,
        sort: state.sort,
    });
    if (state.status) {
        params.set("status", state.status);
    }
    if (state.search) {
        params.set("search", state.search);
    }
    try {
        const data = await request(`${API_URL}?${params}`);
        if (data.items.length === 0 && state.offset > 0) {
            state.offset = Math.max(0, state.offset - PAGE_SIZE);
            return loadTickets({ silent });
        }
        state.total = data.total;
        renderTickets(data.items);
        renderPagination();
    } catch (error) {
        el.list.replaceChildren();
        toast(`Не удалось загрузить заявки: ${error.message}`, "error");
    }
}

async function loadStats() {
    try {
        const stats = await request(`${API_URL}/stats`);
        for (const node of el.stats.querySelectorAll("[data-stat]")) {
            animateNumber(node, stats[node.dataset.stat]);
        }
    } catch (error) {
        toast(`Не удалось загрузить статистику: ${error.message}`, "error");
    }
}

function refreshAll() {
    return Promise.all([loadTickets({ silent: true }), loadStats()]);
}

function setFilter(status) {
    state.status = status;
    state.offset = 0;
    for (const node of el.tabs.querySelectorAll(".tab")) {
        node.classList.toggle("is-active", node.dataset.status === status);
    }
    for (const node of el.stats.querySelectorAll(".stat")) {
        node.classList.toggle("is-active", node.dataset.status === status);
    }
    loadTickets();
}

/* ---------- Drawer ---------- */

function renderTimeline(events) {
    const items = [...events].reverse().map((event) => {
        const li = h("li");
        li.style.setProperty("--dot", STATUS_COLORS[event.new_status]);
        const text = event.old_status === null
            ? "Заявка создана"
            : `${STATUS_LABELS[event.old_status]} → ${STATUS_LABELS[event.new_status]}`;
        li.append(
            h("div", "timeline__text", text),
            h("div", "timeline__time", formatDate(event.created_at)),
        );
        return li;
    });
    el.drawerTimeline.replaceChildren(...items);
}

function renderActions(ticket) {
    const buttons = ticket.allowed_transitions.map((status) => {
        const button = h("button", `btn action--${status}`, actionLabel(ticket.status, status));
        button.addEventListener("click", () => changeStatus(ticket.id, status));
        return button;
    });
    el.drawerActions.replaceChildren(...buttons);
}

function renderDrawer(ticket, events) {
    el.drawerId.textContent = `Заявка #${ticket.id}`;
    el.drawerTitle.textContent = ticket.title;
    el.drawerBadges.replaceChildren(
        statusBadge(ticket.status),
        priorityIndicator(ticket.priority),
    );
    el.drawerEmail.textContent = ticket.customer_email;
    el.drawerCreated.textContent = formatDate(ticket.created_at);
    el.drawerUpdated.textContent = formatDate(ticket.updated_at);
    el.drawerDescription.textContent = ticket.description;
    renderActions(ticket);
    renderTimeline(events);
}

async function openDrawer(ticketId) {
    state.selectedId = ticketId;
    highlightSelected();
    try {
        const [ticket, events] = await Promise.all([
            request(`${API_URL}/${ticketId}`),
            request(`${API_URL}/${ticketId}/events`),
        ]);
        renderDrawer(ticket, events);
        el.drawer.classList.add("is-open");
        el.drawer.setAttribute("aria-hidden", "false");
        el.overlay.hidden = false;
    } catch (error) {
        toast(error.message, "error");
        closeDrawer();
    }
}

function closeDrawer() {
    state.selectedId = null;
    el.drawer.classList.remove("is-open");
    el.drawer.setAttribute("aria-hidden", "true");
    el.overlay.hidden = true;
    highlightSelected();
    resetDeleteButton();
}

async function changeStatus(ticketId, status) {
    for (const button of el.drawerActions.querySelectorAll("button")) {
        button.disabled = true;
    }
    try {
        await request(`${API_URL}/${ticketId}/status`, {
            method: "PATCH",
            body: JSON.stringify({ status }),
        });
        toast(`#${ticketId} → «${STATUS_LABELS[status]}». Клиенту отправлено уведомление`);
        await Promise.all([openDrawer(ticketId), refreshAll()]);
    } catch (error) {
        toast(error.message, "error");
        await openDrawer(ticketId);
    }
}

let deleteConfirmTimer = null;

function resetDeleteButton() {
    clearTimeout(deleteConfirmTimer);
    el.deleteButton.classList.remove("is-confirming");
    el.deleteButton.textContent = "Удалить заявку";
}

async function handleDelete() {
    if (!el.deleteButton.classList.contains("is-confirming")) {
        el.deleteButton.classList.add("is-confirming");
        el.deleteButton.textContent = "Нажмите ещё раз для подтверждения";
        deleteConfirmTimer = setTimeout(resetDeleteButton, 3000);
        return;
    }
    const ticketId = state.selectedId;
    resetDeleteButton();
    try {
        await request(`${API_URL}/${ticketId}`, { method: "DELETE" });
        closeDrawer();
        toast(`Заявка #${ticketId} удалена`);
        await refreshAll();
    } catch (error) {
        toast(error.message, "error");
    }
}

/* ---------- Create modal ---------- */

function openModal() {
    el.formError.hidden = true;
    el.modal.hidden = false;
    requestAnimationFrame(() => el.form.elements.title.focus());
}

function closeModal() {
    el.modal.hidden = true;
    el.form.reset();
}

function showFormError(message) {
    el.formError.textContent = message;
    el.formError.hidden = false;
}

async function handleCreate(event) {
    event.preventDefault();
    const invalidField = el.form.querySelector(":invalid");
    if (invalidField) {
        const label = invalidField.closest(".field").querySelector(".field__label");
        showFormError(`${label.textContent}: ${invalidField.validationMessage}`);
        invalidField.focus();
        return;
    }

    const submit = el.form.querySelector("[type=submit]");
    submit.disabled = true;
    try {
        const payload = Object.fromEntries(new FormData(el.form));
        const ticket = await request(API_URL, {
            method: "POST",
            body: JSON.stringify(payload),
        });
        closeModal();
        toast(`Заявка #${ticket.id} создана`);
        state.offset = 0;
        await refreshAll();
        await openDrawer(ticket.id);
    } catch (error) {
        showFormError(error.message);
    } finally {
        submit.disabled = false;
    }
}

/* ---------- Health ---------- */

async function checkHealth() {
    const text = el.apiStatus.querySelector(".api-status__text");
    try {
        await request("/health");
        el.apiStatus.className = "api-status is-online";
        text.textContent = "API online";
    } catch {
        el.apiStatus.className = "api-status is-offline";
        text.textContent = "API недоступен";
    }
}

/* ---------- Events ---------- */

el.tabs.addEventListener("click", (event) => {
    const tab = event.target.closest(".tab");
    if (tab) {
        setFilter(tab.dataset.status);
    }
});

el.stats.addEventListener("click", (event) => {
    const card = event.target.closest(".stat");
    if (card) {
        setFilter(card.dataset.status);
    }
});

el.list.addEventListener("click", (event) => {
    const row = event.target.closest(".ticket[data-id]");
    if (row) {
        openDrawer(Number(row.dataset.id));
    }
});

let searchTimer = null;

el.search.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        const value = el.search.value.trim();
        if (value === state.search) {
            return;
        }
        state.search = value;
        state.offset = 0;
        loadTickets();
    }, SEARCH_DEBOUNCE_MS);
});

el.sort.addEventListener("change", () => {
    state.sort = el.sort.value;
    state.offset = 0;
    loadTickets();
});

el.prevPage.addEventListener("click", () => {
    state.offset = Math.max(0, state.offset - PAGE_SIZE);
    loadTickets();
});

el.nextPage.addEventListener("click", () => {
    state.offset += PAGE_SIZE;
    loadTickets();
});

el.refresh.addEventListener("click", () => {
    loadTickets();
    loadStats();
});

el.openCreate.addEventListener("click", openModal);
el.form.addEventListener("submit", handleCreate);
el.deleteButton.addEventListener("click", handleDelete);
el.overlay.addEventListener("click", closeDrawer);

el.drawer.querySelector("[data-close]").addEventListener("click", closeDrawer);

for (const button of el.modal.querySelectorAll("[data-close]")) {
    button.addEventListener("click", closeModal);
}

el.modal.addEventListener("click", (event) => {
    if (event.target === el.modal) {
        closeModal();
    }
});

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        if (!el.modal.hidden) {
            closeModal();
        } else {
            closeDrawer();
        }
        return;
    }
    const isTyping = event.target.closest("input, textarea, select");
    if (isTyping || event.ctrlKey || event.metaKey || !el.modal.hidden) {
        return;
    }
    if (event.code === "KeyN") {
        event.preventDefault();
        openModal();
    } else if (event.key === "/") {
        event.preventDefault();
        el.search.focus();
    }
});

setInterval(() => {
    if (el.modal.hidden) {
        refreshAll();
    }
}, AUTO_REFRESH_MS);
setInterval(checkHealth, HEALTH_CHECK_MS);

setFilter("");
loadStats();
checkHealth();
