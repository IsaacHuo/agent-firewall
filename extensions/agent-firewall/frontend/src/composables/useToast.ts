/**
 * Toast notification composable
 *
 * Provides a simple API for showing toast notifications
 */

import { ref } from "vue";
import type { Toast } from "../components/common/Toast.vue";

interface ToastOptions {
  title?: string;
  message: string;
  duration?: number;
}

const toastRef = ref<any>(null);

export function useToast() {
  function setToastRef(ref: any) {
    toastRef.value = ref;
  }

  function showToast(type: Toast["type"], options: ToastOptions | string) {
    if (!toastRef.value) {
      console.warn("Toast component not mounted");
      return;
    }

    const opts = typeof options === "string" ? { message: options } : options;

    return toastRef.value.addToast({
      type,
      ...opts,
    });
  }

  function success(options: ToastOptions | string) {
    return showToast("success", options);
  }

  function error(options: ToastOptions | string) {
    return showToast("error", options);
  }

  function warning(options: ToastOptions | string) {
    return showToast("warning", options);
  }

  function info(options: ToastOptions | string) {
    return showToast("info", options);
  }

  function remove(id: string) {
    if (toastRef.value) {
      toastRef.value.removeToast(id);
    }
  }

  function clearAll() {
    if (toastRef.value) {
      toastRef.value.clearAll();
    }
  }

  return {
    setToastRef,
    success,
    error,
    warning,
    info,
    remove,
    clearAll,
  };
}
