
You’re working with a **modern CTFd theme structure** (v3.0+), which uses **Vite** as a build tool. This is more complex than older versions because the CSS and JS you see in `static/assets` are "compiled"—meaning you don't edit them directly.

Here is the master map of your theme.

---

### 1. Root Directory: The Engine
These files handle how your theme is built and managed.

| File / Folder | Purpose |
| :--- | :--- |
| **`assets/`** | **Crucial:** This is where the *source* code for CSS and JS lives. You edit files here, then "build" them into the static folder. |
| **`static/`** | The "dist" folder. CTFd serves these files to the browser. (Don't edit hashed files here!) |
| **`templates/`** | The HTML files using Jinja2 logic. This is your primary workspace for UI changes. |
| `package.json` | Lists the Node.js dependencies (like Vite, Bootstrap, etc.) needed to build the theme. |
| `vite.config.js` | The configuration for the Vite compiler. It tells the system how to turn your source code into the production files in `static/`. |
| `yarn.lock` | Locks the versions of your dependencies so the build is consistent. |
| `postcss.config.js` | Config for PostCSS (usually for autoprefixing CSS for different browsers). |

---

### 2. Templates Directory: The Skeleton
These files define the structure of every page.

| Sub-folder / File | Purpose |
| :--- | :--- |
| **`base.html`** | The master template. Contains the `<head>`, global CSS links, and the overall structure. |
| **`components/`** | Small, reusable UI pieces like the **navbar.html** or **notifications.html**. |
| **`navbar.html`** | Is the template for your site's navigation bar—the menu at the top of the screen that users see on every page. |
| **`challenges.html`** | The main "Challenge Board" grid view. |
| **`challenge.html`** | The pop-up/modal view when you click a specific challenge. |
| **`scoreboard.html`** | The page showing the rankings and graphs. |
| **`login.html`** / **`register.html`** | User authentication pages. |
| **`users/`** | Templates for user profiles (public and private). |
| **`teams/`** | Templates for team management and team profiles. |
| **`errors/`** | Custom pages for 404 (Not Found) or 500 (Server Error) messages. |
| **`macros/`** | Snippets of code used to generate forms and inputs consistently. |

---

### 3. Static Directory: The Paint
The browser downloads these files to make the site look and act correctly.

| Sub-folder / File | Purpose |
| :--- | :--- |
| **`assets/`** | Contains files like `main.[hash].css`. The `[hash]` changes every time you build. |
| **`img/`** | Where you store the AUPP logo, favicons, and background images. |
| **`webfonts/`** | Local copies of fonts (FontAwesome, Lato, etc.) so the site works offline. |
| **`sounds/`** | The "ding" you hear when a notification or solve happens. |

---

### How to actually make changes (The Workflow)

Since you are using a Vite-based theme, you have two paths:

#### Path A: The "Quick & Dirty" (No Build Required)
If you don't want to mess with Node.js/Yarn:
1.  **HTML:** Edit the files in `templates/` directly.
2.  **CSS:** Open `templates/base.html` and add a `<style>` block right before the `</head>` tag to override the default look.

#### Path B: The "Professional" (Vite Build)
If you want to do a full rewrite of the CSS:
1.  You must have **Node.js** and **Yarn** installed on your Ubuntu machine.
2.  Edit the files inside the root `assets/` folder (the source files).
3.  Run `yarn build` inside the theme folder. This will delete the old files in `static/assets` and create new ones with new hashes.

---

### First Customization Task: Brand your CTFd
Let's make a change you can see immediately without a build.

1.  **Open:** `templates/components/navbar.html`
2.  **Change:** Look for `{{ Configs.ctf_name }}`.
3.  **Action:** Wrap it in a span with a custom class:
    ```html
    <span style="color: #D4AF37; font-weight: bold; letter-spacing: 2px;">
        AUPP | {{ Configs.ctf_name }}
    </span>
    ```
4.  **Check:** Go to your browser, ensure `aupp-custom-theme` is selected in **Admin > Config > Appearance**, and refresh.

**Would you like me to give you a custom "Hacker" CSS block to paste into your `base.html` to instantly change the theme's colors?**
