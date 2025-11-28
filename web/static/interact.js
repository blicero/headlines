// Time-stamp: <2025-11-28 20:01:41 krylon>
// -*- mode: javascript; coding: utf-8; -*-
// Copyright 2015-2020 Benjamin Walkenhorst <krylon@gmx.net>
//
// This file has grown quite a bit larger than I had anticipated.
// It is not a /big/ problem right now, but in the long run, I will have to
// break this thing up into several smaller files.

'use strict';

const whitespace_pat = /^\s*$/

function defined(x) {
    return undefined !== x && null !== x
}

function fmtDateNumber(n) {
    return (n < 10 ? '0' : '') + n.toString()
} // function fmtDateNumber(n)

function timeStampString(t) {
    if ((typeof t) === 'string') {
        return t
    }

    const year = t.getYear() + 1900
    const month = fmtDateNumber(t.getMonth() + 1)
    const day = fmtDateNumber(t.getDate())
    const hour = fmtDateNumber(t.getHours())
    const minute = fmtDateNumber(t.getMinutes())
    const second = fmtDateNumber(t.getSeconds())

    const s =
          year + '-' + month + '-' + day +
          ' ' + hour + ':' + minute + ':' + second
    return s
} // function timeStampString(t)

function fmtDuration(seconds) {
    let minutes = 0
    let hours = 0

    while (seconds > 3599) {
        hours++
        seconds -= 3600
    }

    while (seconds > 59) {
        minutes++
        seconds -= 60
    }

    if (hours > 0) {
        return `${hours}h${minutes}m${seconds}s`
    } else if (minutes > 0) {
        return `${minutes}m${seconds}s`
    } else {
        return `${seconds}s`
    }
} // function fmtDuration(seconds)

function beaconLoop() {
    try {
        if (settings.beacon.active) {
            const req = $.get('/ajax/beacon',
                              {},
                              function (response) {
                                  let status = ''

                                  if (response.Status) {
                                      status = 
                                          response.Message +
                                          ' running on ' +
                                          response.Hostname +
                                          ' is alive at ' +
                                          response.Timestamp
                                  } else {
                                      status = 'Server is not responding'
                                  }

                                  const beaconDiv = $('#beacon')[0]

                                  if (defined(beaconDiv)) {
                                      beaconDiv.innerHTML = status
                                      beaconDiv.classList.remove('error')
                                  } else {
                                      console.log('Beacon field was not found')
                                  }
                              },
                              'json'
                             ).fail(function () {
                                 const beaconDiv = $('#beacon')[0]
                                 beaconDiv.innerHTML = 'Server is not responding'
                                 beaconDiv.classList.add('error')
                                 // logMsg("ERROR", "Server is not responding");
                             })
        }
    } finally {
        window.setTimeout(beaconLoop, settings.beacon.interval)
    }
} // function beaconLoop()

function beaconToggle() {
    settings.beacon.active = !settings.beacon.active
    saveSetting('beacon', 'active', settings.beacon.active)

    if (!settings.beacon.active) {
        const beaconDiv = $('#beacon')[0]
        beaconDiv.innerHTML = 'Beacon is suspended'
        beaconDiv.classList.remove('error')
    }
} // function beaconToggle()

function toggle_hide_boring() {
    const state = !settings.news.hideBoring
    settings.news.hideBoring = state
    saveSetting('news', 'hideBoring', state)
    $("#toggle_hide_boring")[0].checked = state
} // function toggle_hide_boring()

/*
  The ‘content’ attribute of Window objects is deprecated.  Please use ‘window.top’ instead. interact.js:125:8
  Ignoring get or set of property that has [LenientThis] because the “this” object is incorrect. interact.js:125:8

*/

function db_maintenance() {
    const maintURL = '/ajax/db_maint'

    const req = $.get(
        maintURL,
        {},
        function (res) {
            if (!res.Status) {
                console.log(res.Message)
                msg_add('ERROR', res.Message)
            } else {
                const msg = 'Database Maintenance performed without errors'
                console.log(msg)
                msg_add('INFO', msg)
            }
        },
        'json'
    ).fail(function () {
        const msg = 'Error performing DB maintenance'
        console.log(msg)
        msg_add('ERROR', msg)
    })
} // function db_maintenance()

function scale_images() {
    const selector = '#items img'
    const maxHeight = 300
    const maxWidth = 300

    $(selector).each(function () {
        const img = $(this)[0]
        if (img.width > maxWidth || img.height > maxHeight) {
            const size = shrink_img(img.width, img.height, maxWidth, maxHeight)

            img.width = size.width
            img.height = size.height
        }
    })
} // function scale_images()

// Found here: https://stackoverflow.com/questions/3971841/how-to-resize-images-proportionally-keeping-the-aspect-ratio#14731922
function shrink_img(srcWidth, srcHeight, maxWidth, maxHeight) {
    const ratio = Math.min(maxWidth / srcWidth, maxHeight / srcHeight)

    return { width: srcWidth * ratio, height: srcHeight * ratio }
} // function shrink_img(srcWidth, srcHeight, maxWidth, maxHeight)

const max_msg_cnt = 5

function msg_clear() {
    $('#msg_tbl')[0].innerHTML = ''
} // function msg_clear()

function msg_add(msg, level=1) {
    const row = `<tr><td>${new Date()}</td><td>${level}</td><td>${msg}</td><td></td></tr>`
    const msg_tbl = $('#msg_tbl')[0]

    const rows = $('#msg_tbl tr')
    let i = 0
    let cnt = rows.length
    while (cnt >= max_msg_cnt) {
        rows[i].remove()
        i++
        cnt--
    }

    msg_tbl.innerHTML += row
} // function msg_add(msg)

function fmtNumber(n, kind = "") {
    if (kind in formatters) {
        return formatters[kind](n)
    } else {
        return fmtDefault(n)
    }
} // function fmtNumber(n, kind = "")

function fmtDefault(n) {
    return n.toPrecision(3).toString()
} // function fmtDefault(n)

function fmtBytes(n) {
    const units = ["KB", "MB", "GB", "TB", "PB"]
    let idx = 0
    while (n >= 1024) {
        n /= 1024
        idx++
    }

    return `${n.toPrecision(3)} ${units[idx]}`
} // function fmtBytes(n)

const formatters = {
    "sysload": fmtNumber,
    "disk": fmtBytes,
}

function rate_item(item_id, rating) {
    const url = `/ajax/item_rate/${item_id}/${rating}`

    const req = $.post(url,
                       { "item": item_id,
                         "rating": rating },
                       (res) => {
                           if (res.status) {
                               var icon = '';
                               switch (rating) {
                               case 0:
                                   icon = 'face-tired'
                                   const row_id = `#item_row_${item_id}`
                                   const row = $(row_id)[0]
                                   row.classList.add("boring")
                                   break
                               case 1:
                                   icon = 'face-glasses'
                                   break
                               default:
                                   const msg = `Invalid rating: ${rating}`
                                   console.log(msg)
                                   alert(msg)
                                   return
                               }

                               const src = `/static/${icon}.png`
                               const cell = $(`#item_rating_${item_id}`)[0]

                               cell.innerHTML = `<img src="${src}" onclick="unrate_item(${item_id});" />`
                           } else {
                               msg_add(res.message)
                           }
                       },
                       'json')
} // function rate_item(item_id, rating)

function unrate_item(item_id) {
    const url = `/ajax/item_unrate/${item_id}`

    const req = $.post(url,
                      {},
                      (res) => {
                          if (!res.status) {
                              console.log(res.message)
                              msg_add(res.message, 2)
                              return
                          }

                          $(`#item_rating_${item_id}`)[0].innerHTML = res.content

                          const row = $(`#item_row_${item_id}`)[0]
                          row.classList.remove("boring")
                      },
                      'json')
} // function rate_item(item_id, rating)

function clear_form() {
    const form = $("#subscribeForm")[0]
    form.reset()
} // function clear_form()

function get_subscribe_field(name) {
    const id = `#${name}`
    return $(id)[0].value
} // function get_subscribe_field(name)

function subscribe() {
    let data = {
        "title": get_subscribe_field("name"),
        "url": get_subscribe_field("url"),
        "homepage": get_subscribe_field("homepage"),
        "interval": get_subscribe_field("interval"),
    }

    const req = $.post('/ajax/subscribe',
                       data,
                       (res) => {
                           if (res.status) {
                               clear_form()
                           } else {
                               const msg = `Failed to add Feed ${data.title}: ${res.message}`
                               console.log(msg)
                               alert(msg)
                           }
                       },
                       'json'
                      )
} // function subscribe()

function add_tag(item_id) {
    const url = '/ajax/add_tag_link'

    const tag_sel_id = `#item_tag_sel_${item_id}`
    const tag_sel = $(tag_sel_id)[0]
    const tag_opt = tag_sel.selectedOptions[0]
    const tag_id = tag_opt.value
    const tag_label = tag_opt.label.trim()

    const data = {
        "item_id": item_id,
        "tag_id": tag_id,
    }

    const req = $.post(
        url,
        data,
        (res) => {
            if (res.status) {
                tag_opt.disabled = true
                const label = `<span id="tag_link_${item_id}_${tag_id}">
<a href="/tags/${tag_id}">${tag_label}</a>
<img src="/static/delete.png"
     onclick="remove_tag_link(${item_id}, ${tag_id});" />
</span> &nbsp;`
                const tags = $(`#item_tags_${item_id}`)[0]
                tags.innerHTML += label
            } else {
                const msg = res.message
                console.error(msg)
                alert(msg)
            }
        },
        'json'
    ).fail(function () {
        const msg = `Error adding Tag ${tag_id} to Item ${item_id}`
        console.error(msg)
        msg_add('ERROR', msg)
        alert(msg)
    })
} // function add_tag(item_id)

function remove_tag_link(item_id, tag_id) {
    const url = '/ajax/del_tag_link'
    const data = {
        "item_id": item_id,
        "tag_id": tag_id,
    }

    console.log(`About to remove Tag ${tag_id} from Item ${item_id}`)

    const req = $.post(
        url,
        data,
        (res) => {
            if (res.status) {
                // If we wanted to be *really* thorough, we could also disable the
                // tag in the Item's menu. But I don't think that's a high priority
                // issue.
                console.log(`Successfully removed Tag ${tag_id} from Item ${item_id}.`)
                const lbl_id = `#tag_link_${item_id}_${tag_id}`
                const lbl = $(lbl_id)[0]
                lbl.remove()
            } else {
                const msg = res.message
                console.error(msg)
                alert(msg)
            }
        },
        'json'
    ).fail(function () {
        const msg = `Error adding Tag ${tag_id} to Item ${item_id}`
        console.error(msg)
        msg_add('ERROR', msg)
        alert(msg)
    })
} // function remove_tag(item_id, tag_id)

function attach_tag_to_item(item_id, tag_id, elt_id, tag_name) {
    const url = '/ajax/add_tag_link'

    const data = {
        "item_id": item_id,
        "tag_id": tag_id,
    }

    const req = $.post(
        url,
        data,
        (res) => {
            if (res.status) {
                // If we wanted to be *really* thorough, we could also disable the
                // tag in the Item's menu. But I don't think that's a high priority
                // issue.

                const label = `<span id="tag_link_${item_id}_${tag_id}">
<a href="/tags/${tag_id}">${tag_name}</a>
<img src="/static/delete.png"
     onclick="remove_tag_link(${item_id}, ${tag_id});" />
</span> &nbsp;`

                const tags = $(`#item_tags_${item_id}`)[0]
                tags.innerHTML += label

                const elt = $(`#${elt_id}`)[0]
                elt.remove()
            } else {
                const msg = res.message
                console.error(msg)
                alert(msg)
            }
        },
        'json'
    ).fail(function () {
        const msg = `Error adding Tag ${tag_id} to Item ${item_id}`
        console.error(msg)
        msg_add('ERROR', msg)
        alert(msg)
    })
} // function attach_tag_to_item(item_id, tag_id, elt_id, tag_name)

function display_items_for_tag(tag_id) {
    const url = `/ajax/items_by_tag/${tag_id}`

    $.get(
        url,
        {},
        (res) => {
            if (res.status) {
                const div = $("#content-area")[0]
                div.innerHTML = res.payload
            } else {
                console.error(res.message)
                alert(res.message)
            }
        },
        'json'
    ).fail(() => {
        const msg = `Error loading Items by Tag ${tag_id}`
        console.error(msg)
        msg_add('ERROR', msg)
        alert(msg)
    })
} // function display_items_for_tag(tag_id)

function clear_tag_form() {
    const input_name = $("#tag_form_name")[0]
    const input_parent = $("#tag_form_parent")[0]

    input_name.value = ""
    input_parent.selectedIndex = 0
} // function clear_tag_form()

function create_tag() {
    const url = "/ajax/tag/new"
    const input_name = $("#tag_form_name")[0]
    const input_parent = $("#tag_form_parent")[0]
    const input_idx = input_parent.selectedIndex

    const name = input_name.value
    const parent = input_parent[input_idx].value
    const pat = /^\s*$/

    if (name.match(pat) != null) {
        const msg = "Tag name must not be empty!"
        alert(msg)
    }

    const data = { "name": name, "parent": parent }

    $.post(
        url,
        data,
        (res) => {
            if (res.status) {
                location.reload()
            } else {
                console.error(res.message)
                alert(res.message)
            }
        },
        'json'
    ).fail(() => {
        const msg = `Error adding Tag ${name}`
        console.error(msg)
        msg_add('ERROR', msg)
        alert(msg)
    })
} // function create_tag()

function mark_later_read(item_id) {
    const url = `/ajax/later/add/${item_id}`
    const div_id = `#later_${item_id}`
    const div = $(div_id)[0]

    $.post(
        url,
        {},
        (res) => {
            if (res.status) {
                const content = `
<button type="button"
        class="btn btn-dark btn-sm later"
        onclick="mark_later_done(${item_id});">
Done?
</button>
`
                div.innerHTML = content
            } else {
                console.error(res.message)
                msg_add('ERROR', res.message)
                alert(res.message)
            }
        },
        'json'
    ).fail(() => {
        const msg = `Error marking Item ${item_id} as read-later`
        msg_add('ERROR', msg)
        alert(msg)
    })
} // function mark_later_read(item_id)

function mark_later_done(item_id) {
    const url = `/ajax/later/done/${item_id}`
    const div_id = `#later_${item_id}`
    const div = $(div_id)[0]

    $.post(
        url,
        {},
        (res) => {
            if (res.status) {
                div.innerHTML = '' // ???
            } else {
                console.error(res.message)
                msg_add('ERROR', res.message)
                alert(res.message)
            }
        },
        'json'
    ).fail(() => {
        const msg = `Error marking Item ${item_id} as read`
        msg_add('ERROR', msg)
        alert(msg)
    })
} // function mark_later_done(item_id)

function feed_toggle_active(feed_id) {
    const url = `/ajax/feed/toggle_active/${feed_id}`
    $.get(
        url,
        {},
        (res) => {
            if (res.status) {
                // Okeli-dokeli
            } else {
                msg_add('ERROR', res.message)
                console.error(res.message)
                alert(res.message)
            }
        },
        'json'
    ).fail(() => {
        const msg = `Error toggling subscription of Feed ${feed_id}`
        msg_add('ERROR', msg)
        alert(msg)
    })
} // function feed_toggle_active(feed_id)

function feed_unsubscribe(feed_id) {
    const url = `/ajax/feed/unsubscribe/${feed_id}`
    const msg = `IMPLEMENTME: feed_unsubscribe(${feed_id})`
    console.log(msg)
    alert(msg)
} // function feed_unsubscribe(feed_id)

function feed_interval_edit(feed_id, current) {
    const cell_id = `#feed_interval_${feed_id}`
    const cell = $(cell_id)[0]

    const cell_content = `
<input type="number"
       id="feed_interval_input_${feed_id}"
       name="feed_interval_input_${feed_id}"
       min="300"
       max="86400"
       step="60"
       value="${current}"/>
<button type="button"
        class="btn btn-sm btn-success"
        onclick="feed_interval_submit(${feed_id});">
  OK
</button>
<button type="button"
        class="btn btn-sm btn-danger"
        onclick="feed_interval_cancel(${feed_id}, ${current});">
  Cancel
</button>
`
    cell.innerHTML = cell_content
} // function feed_interval_edit(feed_id)

function feed_interval_submit(feed_id) {
    const cell_id = `#feed_interval_${feed_id}`
    const cell = $(cell_id)[0]
    const input_id = `#feed_interval_input_${feed_id}`
    const input = $(input_id)[0]
    const new_interval = input.value
    const url = `/ajax/feed/set_interval/${feed_id}/${new_interval}`

    $.get(
        url,
        {},
        (res) => {
            if (res.status) {
                const cell_content = `
<span onclick="feed_interval_edit(${feed_id}, ${new_interval});"
      id="feed_interval_${feed_id}">
  ${new_interval}
</span>
`
                cell.innerHTML = cell_content
            } else {
                msg_add('ERROR', res.message)
                alert(res.message)
            }
        },
        'json'
    ).fail(() => {
        const msg = `Error setting interval for Feed ${feed_id}`
        msg_add('ERROR', msg)
        alert(msg)
    })

} // function feed_interval_submit(feed_id)

function feed_interval_cancel(feed_id, interval) {
    const cell_id = `#feed_interval_${feed_id}`
    const cell = $(cell_id)[0]

    cell.innerHTML = `
<span onclick="feed_interval_edit(${feed_id}, ${interval});"
      id="feed_interval_${feed_id}">
  ${interval}
</span>
`
} // function feed_interval_cancel(feed_id, interval)

var bl_pat_valid_res = false

function bl_pat_valid_notify() {
    if (bl_pat_valid_res) {
        const res_id = "#bl_pat_check_res"
        $(res_id)[0].innerHTML = ""
        bl_pat_valid_res = false
    }
} // function bl_pat_valid_notify()

function bl_pat_input_clear() {
    const res_id = "#bl_pat_check_res"
    const input_id = "#bl_pat_input"

    $(input_id)[0].value = ""
    $(res_id)[0].innerHTML = ""
    bl_pat_valid_res = false
}


function bl_pat_check() {
    const url = "/ajax/blacklist/check"
    const input_id = "#bl_pat_input"
    const res_id = "#bl_pat_check_res"
    const txt = $(input_id)[0].value

    if (whitespace_pat.test(txt)) {
        const msg = 'Blacklist pattern to test is only whitespace'
        msg_add(msg, 'INFO')
        console.log(msg)
        return
    }

    $.post(
        url,
        { "pattern": txt },
        (res) => {
            if (res.status) {
                bl_pat_valid_res = true
                $(res_id)[0].innerHTML =
                    `<img src="/static/icon_ok.png" />`
            } else {
                bl_pat_valid_res = true
                $(res_id)[0].innerHTML =
                    `<img src="/static/dialog-error.png" />`
            }
        },
        'json'
    ).fail((reply, status_text, xhr) => {
        const msg = `Error checking blacklist pattern: ${status_text} - ${reply}`
        msg_add(msg, 'ERROR')
        console.error(msg)
        alert(msg)
    })

    
} // function bl_pat_check()

function bl_pat_save() {
    const url = "/ajax/blacklist/add"
    const input_id = "#bl_pat_input"
    const pat = $(input_id)[0].value

    $.post(
        url,
        {"pattern": pat},
        (res) => {
            if (res.status) {
                const item_list_id = "#bl_items"
                const item_list = $(item_list_id)[0]
                const dpat = "`" + pat + "`"
                const item_id = res.payload
                const row = `<tr>
    <td class="num">${item_id}</td>
    <td id="bl_pat_${item_id}">${pat}</td>
    <td class="num">0</td>
    <td>
      <button type="button"
              class="btn btn-sm"
              onclick="bl_pat_edit(${item_id}, ${dpat});">Edit</button>
      &nbsp;
      <a href="#"
         onclick="bl_item_delete(${item_id});">
        <img src="/static/delete.png" />
      </a>
    </td>
</tr>`
                item_list.innerHTML += row
                $(input_id)[0].value = ""
            } else {
                msg_add(res.message, 'ERROR')
                alert(res.message)
            }
        },
        'json'
    ).fail((reply, status, xhr) => {
        const msg = `Error checking blacklist pattern: ${status_text} - ${reply}`
        msg_add(msg, 'ERROR')
        console.error(msg)
        alert(msg)
    })
} // function bl_pat_save()

var bl_pat_restore = {}

function bl_pat_edit(item_id, pat) {
    const bl_pat_cell_id = `#bl_pat_${item_id}`
    const bl_pat_cell = $(bl_pat_cell_id)[0]

    bl_pat_restore[item_id] = pat
    bl_pat_cell.innerHTML = `
<input type="text" id="bl_pat_input_${item_id}" value="${pat}" />
<button type="button" class="btn btn-sm btn-success" onclick="bl_pat_update(${item_id});">Save</button>
<button type="button" class="btn btn-sm btn-danger" onclick="bl_pat_edit_cancel(${item_id})">Cancel</button>
`
} // function bl_pat_edit(item_id, pat)

function bl_pat_update(item_id) {
    const url = `/ajax/blacklist/update/${item_id}`
    const cell_id = `#bl_pat_${item_id}`
    const cell = $(cell_id)[0]
    const input_id = `#bl_pat_input_${item_id}`
    const input = $(input_id)[0]

    const new_pat = input.value

    $.post(
        url,
        { "pattern": new_pat },
        (res) => {
            if (res.status) {
                cell.innerHTML = new_pat
                delete bl_pat_restore[item_id]
            } else {
                msg_add(res.message, 'ERROR')
                alert(msg)
            }
        },
        'json'
    ).fail((reply, status, xhr) => {
        const msg = `Error updating blacklist pattern: ${status_text} - ${reply}`
        msg_add(msg, 'ERROR')
        console.error(msg)
        alert(msg)
    })
} // function bl_pat_update(item_id)

function bl_pat_edit_cancel(item_id) {
    const cell_id = `#bl_pat_${item_id}`
    const cell = $(cell_id)[0]

    cell.innerHTML = bl_pat_restore[item_id]
    delete bl_pat_restore[item_id]
} // function bl_pat_edit_cancel(item_id)

function bl_item_delete(item_id) {
    const url = `/ajax/blacklist/delete/${item_id}`
    $.post(
        url,
        {},
        (res) => {
            if (res.status) {
                const row_id = `#bl_pat_row_${item_id}`
                $(row_id).remove()
            }
        },
        'json'
    ).fail((reply, status, xhr) => {
        const msg = `Error deleting blacklist pattern: ${status_text} - ${reply}`
        msg_add(msg, 'ERROR')
        console.error(msg)
        alert(msg)
    })
} // function bl_item_delete(item_id)
