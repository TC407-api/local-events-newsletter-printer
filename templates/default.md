# {{ newsletter_name }}

## {{ date_range }}

{{ intro }}

### 🔥 Don't Miss This Week

{% for event in highlights %}
**{{ event.title }}** at {{ event.venue.name }}
{{ event.day }}, {{ event.date }} • {{ event.time }} • {{ event.price }}

{{ event.description }}

{% if event.ticket_url %}[Get Tickets]({{ event.ticket_url }}){% endif %}

---

{% endfor %}

### 🎵 Live Music & Concerts

{% for day_group in music_events_by_day %}
**{{ day_group.day }}**
{% for event in day_group.events %}

- **{{ event.title }}** - {{ event.time }} | {{ event.price }} | {{ event.venue.name }}{% if event.is_reggae %} 🌴{% endif %}
  {% endfor %}

{% endfor %}

### 🍺 Food & Drink

{% for event in food_events %}

- **{{ event.title }}** - {{ event.venue.name }}, {{ event.day }} {{ event.time }} ({{ event.price }})
  {% endfor %}

### 🎨 Arts & Culture

{% for event in arts_events %}

- **{{ event.title }}** - {{ event.venue.name }}, {{ event.day }} {{ event.time }}
  {% endfor %}

### 📅 Quick Hits

{% for event in other_events %}

- **{{ event.title }}** - {{ event.venue.name }}, {{ event.day }} {{ event.time }}
  {% endfor %}

---

_{{ newsletter_name }} curates the best events in {{ location }}._
_Got an event to share? Reply to this email._
