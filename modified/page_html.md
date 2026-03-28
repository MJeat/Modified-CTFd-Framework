
Original version:

```
{% extends "base.html" %}

{% block content %}
  <div class="container">
    {{ content | safe }}
  </div>
{% endblock %}

{% block scripts %}
  {{ Assets.js("assets/js/page.js") }}
{% endblock %}
```


Updated Version:

```
{% extends "base.html" %}

{% block content %}
  {# Check if we are on the writeups route #}
  {% if request.path == '/writeups' %}
    <div class="jumbotron bg-transparent border-bottom border-success rounded-0">
        <div class="container text-center">
            <h1 class="display-4 font-weight-bold" style="text-shadow: 0 0 10px var(--hacker-green);">[INTEL_REPOSITORY]</h1>
            <p class="lead text-success">> ACCESSING ARCHIVED EXPLOITS... DONE.</p>
        </div>
    </div>

    <div class="container">
        <div class="row">
            <div class="col-md-12 p-4" style="background: rgba(0, 255, 65, 0.05); border: 1px solid var(--hacker-green);">
                <h2 class="text-success border-bottom border-success pb-2">SQL Injection 101</h2>
                <p>Add your hardcoded solutions here!</p>
                <pre class="bg-black text-white p-3 border border-secondary"><code>' OR 1=1 --</code></pre>
            </div>
        </div>
    </div>

  {# This is the safe fallback for other pages #}
  {% else %}
    <div class="container mt-5">
        <h1 class="text-success">{{ page.title if page else "INFORMATION" }}</h1>
        <hr class="bg-success">
        <div class="text-white">
            {# Use 'content' for the homepage and 'page.content' for others #}
            {{ content | safe if content else '' }}
            {{ page.content | safe if page else '' }}
        </div>
    </div>
  {% endif %}
{% endblock %}

{% block scripts %}
  {{ Assets.js("assets/js/page.js") }}
{% endblock %}

```

