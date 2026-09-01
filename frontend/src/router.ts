import { createRouter, createWebHashHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', component: () => import('./views/LoginView.vue') },
    { path: '/teacher', component: () => import('./views/TeacherView.vue') },
    { path: '/display', component: () => import('./views/DisplayView.vue') },
    { path: '/admin', component: () => import('./views/AdminView.vue') },
    { path: '/server', component: () => import('./views/ServerView.vue') },
  ],
})
