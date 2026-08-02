/* Shared demo data + helpers for platform-meals mockups */
const ICONS = {
  duck: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5c-3 0-6 2-6 5 0 1.5.7 2.8 1.8 3.7L6 20h4l1-3h2l1 3h4l-1.8-6.3C17.3 12.8 18 11.5 18 10c0-3-3-5-6-5z"/><circle cx="10" cy="9" r="0.8" fill="currentColor"/></svg>`,
  sandwich: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11h18v2a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4v-2z"/><path d="M3 11V9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2"/><path d="M7 7V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v2"/></svg>`,
  pizza: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="m12 2 9 19H3L12 2z"/><circle cx="12" cy="11" r="1" fill="currentColor"/><circle cx="9" cy="15" r="1" fill="currentColor"/><circle cx="15" cy="14" r="1" fill="currentColor"/></svg>`,
  fish: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 12c0-4 4-7 9.5-7 2 3 2 11 0 14-5.5 0-9.5-3-9.5-7z"/><path d="M6.5 12H3l2-3M6.5 12H3l2 3"/><circle cx="15" cy="10" r="0.8" fill="currentColor"/></svg>`,
  salad: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4c-2 3-6 4-8 4 1 5 4 9 8 11 4-2 7-6 8-11-2 0-6-1-8-4z"/><path d="M12 4v16"/></svg>`,
  bowl: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M4 11h16a8 8 0 0 1-16 0z"/><path d="M8 7c1-2 2.5-3 4-3s3 1 4 3"/></svg>`,
  pastry: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="14" rx="8" ry="5"/><path d="M6 13c1-4 3-7 6-8 3 1 5 4 6 8"/></svg>`,
  curry: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14l-1 6a3 3 0 0 1-3 2H9a3 3 0 0 1-3-2l-1-6z"/><path d="M9 12V8a3 3 0 0 1 6 0v4"/></svg>`,
  toast: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M5 8c0-2 2-4 7-4s7 2 7 4v10a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V8z"/><path d="M9 13h6M9 16h4"/></svg>`,
  soup: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h16v2a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6v-2z"/><path d="M8 9c.5-1 1-2 2-2M12 8c.5-1 1-2 2-2M16 9c.5-1 1-2 2-2"/></svg>`,
  camera: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>`,
  image: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>`,
  book: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`,
  search: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>`,
  x: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>`,
  plus: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5v14"/></svg>`,
  home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
  history: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>`,
  pills: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/><path d="m8.5 8.5 7 7"/></svg>`,
  user: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>`,
  sparkles: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/></svg>`,
};

const PLATFORM_MEALS = [
  {
    id: 'pm-arroz',
    name: 'Arroz de pato',
    cuisine: 'Portuguese',
    icon: 'duck',
    tone: 'amber',
    ingredients: ['Duck', 'Rice', 'Chorizo', 'Orange zest', 'Bay leaf'],
    flags: ['high-histamine'],
  },
  {
    id: 'pm-bifana',
    name: 'Bifana',
    cuisine: 'Portuguese',
    icon: 'sandwich',
    tone: 'rose',
    ingredients: ['Pork', 'Bread', 'Garlic', 'White wine', 'Piri-piri'],
    flags: ['gluten', 'high-histamine'],
  },
  {
    id: 'pm-francesinha',
    name: 'Francesinha',
    cuisine: 'Portuguese',
    icon: 'sandwich',
    tone: 'rose',
    ingredients: ['Bread', 'Steak', 'Ham', 'Sausage', 'Cheese', 'Beer sauce'],
    flags: ['gluten', 'dairy', 'high-histamine'],
  },
  {
    id: 'pm-nata',
    name: 'Pastel de nata',
    cuisine: 'Portuguese',
    icon: 'pastry',
    tone: 'amber',
    ingredients: ['Puff pastry', 'Egg yolk', 'Milk', 'Sugar', 'Cinnamon'],
    flags: ['gluten', 'dairy'],
  },
  {
    id: 'pm-salmon',
    name: 'Grilled salmon',
    cuisine: 'Simple',
    icon: 'fish',
    tone: 'sky',
    ingredients: ['Salmon', 'Olive oil', 'Lemon', 'Dill'],
    flags: ['high-histamine'],
  },
  {
    id: 'pm-greek',
    name: 'Greek salad',
    cuisine: 'Mediterranean',
    icon: 'salad',
    tone: 'sage',
    ingredients: ['Tomato', 'Cucumber', 'Feta', 'Olive', 'Onion'],
    flags: ['dairy'],
  },
  {
    id: 'pm-tikka',
    name: 'Chicken tikka masala',
    cuisine: 'Indian',
    icon: 'curry',
    tone: 'rose',
    ingredients: ['Chicken', 'Tomato', 'Cream', 'Garam masala', 'Garlic'],
    flags: ['dairy'],
  },
  {
    id: 'pm-avo',
    name: 'Avocado toast',
    cuisine: 'Simple',
    icon: 'toast',
    tone: 'sage',
    ingredients: ['Sourdough', 'Avocado', 'Lemon', 'Chili flakes'],
    flags: ['gluten'],
  },
  {
    id: 'pm-ramen',
    name: 'Shoyu ramen',
    cuisine: 'Japanese',
    icon: 'soup',
    tone: 'slate',
    ingredients: ['Noodles', 'Pork broth', 'Egg', 'Nori', 'Scallion'],
    flags: ['gluten', 'high-histamine'],
  },
  {
    id: 'pm-risotto',
    name: 'Mushroom risotto',
    cuisine: 'Italian',
    icon: 'bowl',
    tone: 'slate',
    ingredients: ['Arborio rice', 'Mushroom', 'Parmesan', 'Butter', 'Onion'],
    flags: ['dairy'],
  },
];

const YOUR_MEALS = [
  { id: 'ym-oats', name: 'Overnight oats', when: 'Yesterday', times: 12, flags: ['dairy'], photo: 'oats' },
  { id: 'ym-eggs', name: 'Scrambled eggs', when: 'Today', times: 8, flags: [], photo: 'eggs' },
  { id: 'ym-salad', name: 'Chicken salad', when: 'Wed', times: 3, flags: [], photo: 'salad' },
  { id: 'ym-soup', name: 'Tomato soup', when: 'Mon', times: 2, flags: [], photo: 'soup' },
];

const CATALOG_INGREDIENTS = [
  { name: 'Duck', flags: ['high-histamine'], hist: 2 },
  { name: 'Rice', flags: [], hist: 0 },
  { name: 'Chorizo', flags: ['high-histamine'], hist: 3 },
  { name: 'Orange zest', flags: [], hist: 0 },
  { name: 'Bay leaf', flags: [], hist: 0 },
  { name: 'Pork', flags: [], hist: 1 },
  { name: 'Bread', flags: ['gluten'], hist: 0 },
  { name: 'Garlic', flags: ['high-fodmap'], hist: 0 },
  { name: 'Cheese', flags: ['dairy', 'high-histamine'], hist: 2 },
  { name: 'Tomato', flags: ['high-histamine'], hist: 1 },
  { name: 'Salmon', flags: ['high-histamine'], hist: 2 },
  { name: 'Egg', flags: [], hist: 0 },
  { name: 'Avocado', flags: ['high-fodmap'], hist: 0 },
  { name: 'Olive oil', flags: [], hist: 0 },
  { name: 'Lemon', flags: [], hist: 0 },
  { name: 'Onion', flags: ['high-fodmap'], hist: 0 },
  { name: 'Chicken', flags: [], hist: 0 },
  { name: 'Cream', flags: ['dairy'], hist: 0 },
  { name: 'Mushroom', flags: ['high-fodmap'], hist: 1 },
  { name: 'Parmesan', flags: ['dairy', 'high-histamine'], hist: 3 },
];

function flagPills(flags) {
  if (!flags || !flags.length) return '';
  const map = {
    'high-histamine': ['Histamine', 'hist'],
    'high-fodmap': ['FODMAP', 'fod'],
    gluten: ['Gluten', 'glu'],
    dairy: ['Dairy', 'dai'],
  };
  return `<span class="flags">${flags.map(f => {
    const [label, cls] = map[f] || [f, 'hist'];
    return `<span class="flag ${cls}">${label}</span>`;
  }).join('')}</span>`;
}

function iconThumb(icon, tone = '') {
  return `<div class="icon-tile ${tone}">${ICONS[icon] || ICONS.bowl}</div>`;
}

function photoThumb(kind) {
  const gradients = {
    oats: 'linear-gradient(135deg,#d4a574,#8b6914)',
    eggs: 'linear-gradient(135deg,#f5d76e,#e8a838)',
    salad: 'linear-gradient(135deg,#7cb342,#558b2f)',
    soup: 'linear-gradient(135deg,#e57373,#c62828)',
  };
  return `<div class="photo-fake" style="background:${gradients[kind] || gradients.oats}"></div>`;
}

function showToast(msg) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => el.classList.remove('show'), 2200);
}

function openSheet(id) {
  document.getElementById('scrim')?.classList.add('open');
  document.getElementById(id)?.classList.add('open');
}
function closeSheets() {
  document.getElementById('scrim')?.classList.remove('open');
  document.querySelectorAll('.sheet').forEach(s => s.classList.remove('open'));
}

function phoneChrome(title, subtitle) {
  return `
    <div class="phone-status"><span>14:41</span><span>●●● 5G ▮</span></div>
    <div class="toast" id="toast"></div>
    <div class="phone-body">
      <div class="app-header">
        <div class="title">${title}</div>
        <div class="sub">${subtitle}</div>
      </div>
  `;
}

function bottomNav() {
  return `
    <nav class="bottom-nav">
      <div class="nav-item on">${ICONS.home}<span>Today</span></div>
      <div class="nav-item">${ICONS.history}<span>History</span></div>
      <div class="nav-item">${ICONS.pills}<span>Treatments</span></div>
      <div class="nav-item">${ICONS.user}<span>Profile</span></div>
    </nav>`;
}

function dietRiskBlock(hasMeals) {
  if (hasMeals) {
    return `
      <div>
        <div class="label-sm" style="margin-bottom:8px">Diet risk</div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:6px">
          <span class="locked-chip">Histamine <span class="score">5</span></span>
        </div>
        <p class="text-2xs muted" style="margin-bottom:8px">Histamine: Duck, Chorizo · From meals</p>
        <div class="text-xs muted" style="margin-bottom:6px">Add anything else you ate or drank</div>
        <div class="diet-grid">
          <button class="diet-pill" type="button" data-diet>Alcohol</button>
          <button class="diet-pill" type="button" data-diet>Caffeine</button>
          <button class="diet-pill" type="button" data-diet>Ultra-processed</button>
          <button class="diet-pill" type="button" data-diet>Spicy</button>
        </div>
      </div>`;
  }
  return `
    <div>
      <div class="label-sm" style="margin-bottom:8px">Diet risk</div>
      <div class="diet-info">${ICONS.camera}<span>No food photos for today — anything below is fully manual.</span></div>
      <div class="text-xs muted" style="margin:8px 0 6px">Add anything you ate or drank</div>
      <div class="diet-grid">
        <button class="diet-pill" type="button" data-diet>Alcohol</button>
        <button class="diet-pill" type="button" data-diet>Caffeine</button>
        <button class="diet-pill" type="button" data-diet>Ultra-processed</button>
        <button class="diet-pill" type="button" data-diet>Spicy</button>
      </div>
    </div>`;
}

function wireDietPills(root = document) {
  root.querySelectorAll('[data-diet]').forEach(btn => {
    btn.addEventListener('click', () => btn.classList.toggle('on'));
  });
}
