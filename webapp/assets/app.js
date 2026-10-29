(() => {
  const tg = window.Telegram?.WebApp;
  const initData = tg?.initData || "";
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[ch]));
  const traitNames = {stability:"Уст.",energy:"Энерг.",resonance:"Резон.",adaptation:"Адапт.",complexity:"Сложн."};
  const eventNames = {
    user_entered:"Участник вошёл во вселенную",
    artifact_created:"Создан новый артефакт",
    artifact_mutated:"Записана мутация",
    colony_created:"Основана новая колония",
    artifact_settled:"Артефакт поселён в колонии"
  };

  if (tg) {
    tg.ready();
    tg.expand();
    tg.setHeaderColor?.("#090d16");
    tg.setBackgroundColor?.("#090d16");
  }

  function notify(message, isError=false) {
    const el = $("notice");
    el.textContent = message;
    el.classList.toggle("error", isError);
    el.classList.remove("hidden");
    window.clearTimeout(notify.timer);
    notify.timer = window.setTimeout(() => el.classList.add("hidden"), 4200);
  }

  async function api(path, options={}) {
    if (!initData) throw new Error("Открой Mini App через кнопку в Telegram-боте.");
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type":"application/json",
        "X-Telegram-Init-Data":initData,
        ...(options.headers || {})
      }
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Не удалось выполнить запрос.");
    return data;
  }

  function empty(message) { return '<div class="empty">' + esc(message) + '</div>'; }
  function stat(label, value, accent=false) {
    return '<div class="stat-card"><div class="stat-label">'+esc(label)+'</div><div class="stat-value '+(accent?'cyan':'')+'">'+esc(value)+'</div></div>';
  }
  function genomeMarkup(genome) {
    return '<div class="genome">'+Object.entries(genome || {}).map(([key,value]) =>
      '<div class="trait"><div class="trait-name">'+esc(traitNames[key] || key)+'</div><div class="trait-value">'+esc(value)+'</div><div class="bar"><i style="width:'+Math.max(0,Math.min(100,Number(value)||0))+'%"></i></div></div>'
    ).join("")+'</div>';
  }
  function artifactMarkup(item, withActions=true) {
    return '<article class="item-card"><div class="item-top"><div><div class="item-title">'+esc(item.name)+'</div><div class="item-sub">'+esc(item.code)+' · поколение '+esc(item.generation)+'</div></div><span class="tag">ЭХО</span></div>'+
      (item.genome ? genomeMarkup(item.genome) : '')+
      (withActions ? '<div class="actions"><button class="action" data-mutate="'+esc(item.code)+'">⟁ Развить</button><button class="action" data-copy="'+esc(item.code)+'">Копировать код</button></div>' : '')+
      '</article>';
  }

  async function loadUniverse() {
    const data = await api("/api/universe");
    const s = data.stats;
    $("stats").innerHTML = stat("УЧАСТНИКИ",s.users)+stat("АРТЕФАКТЫ",s.artifacts,true)+stat("КОЛОНИИ",s.colonies)+stat("СОБЫТИЯ",s.events);
    $("recent").innerHTML = data.recent_artifacts.length
      ? data.recent_artifacts.map(item => '<article class="item-card"><div class="item-top"><div><div class="item-title">'+esc(item.name)+'</div><div class="item-sub">'+esc(item.code)+'</div></div><span class="tag">ПОКОЛЕНИЕ '+esc(item.generation)+'</span></div></article>').join("")
      : empty("Пока нет артефактов. Создай первое Эхо в разделе «Артефакты».");
  }

  async function loadArtifacts() {
    const data = await api("/api/artifacts");
    $("artifacts-list").innerHTML = data.items.length
      ? data.items.map(item => artifactMarkup(item)).join("")
      : empty("Твои артефакты появятся здесь. Создай первое Эхо.");
  }

  async function loadColonies() {
    const data = await api("/api/colonies");
    $("colonies-list").innerHTML = data.items.length
      ? data.items.map(item => '<article class="item-card"><div class="item-top"><div><div class="item-title">'+esc(item.name)+'</div><div class="item-sub">Участников: '+esc(item.members)+' · Артефактов: '+esc(item.artifacts)+'</div></div><span class="tag">КОЛОНИЯ</span></div><div class="actions"><button class="action" data-colony="'+esc(item.name)+'">Открыть</button><button class="action" data-settle="'+esc(item.name)+'">＋ Поселить Эхо</button></div></article>').join("")
      : empty("Колоний пока нет. Основать первую можно прямо здесь.");
  }

  async function loadEvents() {
    const data = await api("/api/events");
    $("events-list").innerHTML = data.items.length
      ? data.items.map(item => '<article class="event"><div class="event-title">'+esc(eventNames[item.type] || item.type)+'</div><div class="item-sub">'+(item.artifact_code ? esc(item.artifact_code) : '')+'</div><div class="event-date">'+esc(item.created_at)+'</div></article>').join("")
      : empty("Летопись пока пуста.");
  }

  const loaders = {universe:loadUniverse,artifacts:loadArtifacts,colonies:loadColonies,chronicle:loadEvents};
  async function openPage(page) {
    document.querySelectorAll(".tab").forEach(button => button.classList.toggle("active",button.dataset.page===page));
    document.querySelectorAll(".page").forEach(section => section.classList.toggle("active",section.id==="page-"+page));
    try { await loaders[page](); }
    catch (error) { notify(error.message,true); }
  }

  document.querySelectorAll(".tab").forEach(button => button.addEventListener("click",() => openPage(button.dataset.page)));
  $("new-artifact").addEventListener("click",() => $("artifact-dialog").showModal());
  $("new-colony").addEventListener("click",() => $("colony-dialog").showModal());

  $("artifact-form").addEventListener("submit",async event => {
    if (event.submitter?.value !== "default") return;
    event.preventDefault();
    try {
      const data = await api("/api/artifacts",{method:"POST",body:JSON.stringify({name:$("artifact-name").value})});
      $("artifact-dialog").close();
      $("artifact-name").value = "";
      notify("Артефакт "+data.artifact.code+" создан.");
      await loadArtifacts();
      await loadUniverse();
    } catch(error) { notify(error.message,true); }
  });

  $("colony-form").addEventListener("submit",async event => {
    if (event.submitter?.value !== "default") return;
    event.preventDefault();
    try {
      const data = await api("/api/colonies",{method:"POST",body:JSON.stringify({name:$("colony-name").value})});
      $("colony-dialog").close();
      $("colony-name").value = "";
      notify("Колония «"+data.name+"» основана.");
      await loadColonies();
      await loadUniverse();
    } catch(error) { notify(error.message,true); }
  });

  $("settle-form").addEventListener("submit",async event => {
    if (event.submitter?.value !== "default") return;
    event.preventDefault();
    const name = $("settle-colony").value;
    try {
      await api("/api/colonies/"+encodeURIComponent(name)+"/settle",{method:"POST",body:JSON.stringify({artifact_code:$("settle-code").value})});
      $("settle-dialog").close();
      $("settle-code").value = "";
      notify("Артефакт поселён в колонии «"+name+"».");
      await loadColonies();
    } catch(error) { notify(error.message,true); }
  });

  document.addEventListener("click",async event => {
    const mutate = event.target.closest("[data-mutate]");
    const settle = event.target.closest("[data-settle]");
    const colony = event.target.closest("[data-colony]");
    const copy = event.target.closest("[data-copy]");
    if (mutate) {
      mutate.disabled = true;
      try {
        const data = await api("/api/artifacts/"+encodeURIComponent(mutate.dataset.mutate)+"/mutate",{method:"POST",body:"{}"});
        notify("Записана мутация. Поколение "+data.artifact.generation+".");
        await loadArtifacts(); await loadUniverse();
      } catch(error) { notify(error.message,true); mutate.disabled=false; }
    }
    if (settle) {
      $("settle-colony").value = settle.dataset.settle;
      $("settle-dialog").showModal();
    }
    if (colony) {
      try {
        const data = await api("/api/colonies/"+encodeURIComponent(colony.dataset.colony)+"/artifacts");
        const list = data.items.length ? data.items.map(item => '<div class="item-sub">'+esc(item.name)+' · '+esc(item.code)+' · поколение '+esc(item.generation)+'</div>').join("") : '<div class="item-sub">Пока нет поселённых артефактов.</div>';
        notify("Колония «"+data.colony.name+"»: "+data.colony.members+" участников, "+data.colony.artifacts+" артефактов.");
        const card = colony.closest(".item-card");
        let details = card.querySelector(".colony-details");
        if (!details) { details=document.createElement("div"); details.className="colony-details"; details.style.marginTop="12px"; card.append(details); }
        details.innerHTML = list;
      } catch(error) { notify(error.message,true); }
    }
    if (copy) {
      try {
        await navigator.clipboard.writeText(copy.dataset.copy);
        notify("Код скопирован.");
      } catch { notify("Не удалось скопировать код.",true); }
    }
  });

  async function boot() {
    if (!initData) {
      $("connection").innerHTML = "<span></span> ОЖИДАЕТ TELEGRAM";
      $("stats").innerHTML = empty("Открой это приложение через кнопку ECHOCHAIN в Telegram, чтобы войти в свою вселенную.");
      $("recent").innerHTML = "";
      return;
    }
    try {
      const user = await api("/api/me");
      $("greeting").innerHTML = "Вселенная<br><em>"+esc(user.first_name || "помнит всё.")+"</em>";
      $("connection").innerHTML = "<span></span> ONLINE";
      await loadUniverse();
    } catch(error) {
      $("connection").innerHTML = "<span></span> ОШИБКА";
      notify(error.message,true);
    }
  }
  boot();
})();
