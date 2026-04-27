use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, PhysicalPosition, WindowEvent,
};

#[cfg(target_os = "macos")]
use tauri::ActivationPolicy;

pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(ActivationPolicy::Accessory);

            let main_window = app.get_webview_window("main").unwrap();
            main_window.hide().unwrap();

            let open_item = MenuItem::with_id(app, "open", "Open MOCA", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open_item, &quit_item])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        position,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(win) = app.get_webview_window("main") {
                            if win.is_visible().unwrap_or(false) {
                                let _ = win.hide();
                            } else {
                                position_window(win, position);
                            }
                        }
                    }
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                window.hide().unwrap();
            }
        })
        .run(tauri::generate_context!())
        .expect("error running MOCA");
}

fn position_window(win: tauri::WebviewWindow, click_pos: PhysicalPosition<f64>) {
    let window_size = win
        .outer_size()
        .unwrap_or(tauri::PhysicalSize { width: 400, height: 600 });

    #[cfg(target_os = "macos")]
    {
        let x = click_pos.x as i32 - (window_size.width as i32 / 2);
        let y = click_pos.y as i32 + 8;
        let _ = win.set_position(PhysicalPosition { x, y });
    }

    #[cfg(not(target_os = "macos"))]
    {
        if let Some(monitor) = win.primary_monitor().ok().flatten() {
            let screen = monitor.size();
            let x = screen.width as i32 - window_size.width as i32 - 16;
            let y = screen.height as i32 - window_size.height as i32 - 48;
            let _ = win.set_position(PhysicalPosition { x, y });
        }
    }

    let _ = win.show();
    let _ = win.set_focus();
}
