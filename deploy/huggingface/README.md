---
title: SPHEREx Visor API
emoji: 🔭
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: API del visor SPHEREx (Hackathon NASA, HackatonNASA)
---

Backend del visor web de SPHEREx: coordenadas → serie de imágenes en el tiempo, 102 bandas,
máscaras de FLAGS, espectros y resta de cuadros. Código: https://github.com/ignacisolis/HACKATON

- Documentación interactiva: `/docs`
- Salud: `/api/health` · Objetivos de la demo: `/api/targets`
- Ejemplo: `/api/frames?target=wise_0855&detector=D6`
