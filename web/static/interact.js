// Time-stamp: <2025-10-29 17:00:51 krylon>
// -*- mode: javascript; coding: utf-8; -*-
// Copyright 2015-2020 Benjamin Walkenhorst <krylon@gmx.net>
//
// This file has grown quite a bit larger than I had anticipated.
// It is not a /big/ problem right now, but in the long run, I will have to
// break this thing up into several smaller files.

'use strict';

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
                msg_add(new Date(), 'ERROR', res.Message)
            } else {
                const msg = 'Database Maintenance performed without errors'
                console.log(msg)
                msg_add(new Date(), 'INFO', msg)
            }
        },
        'json'
    ).fail(function () {
        const msg = 'Error performing DB maintenance'
        console.log(msg)
        msg_add(new Date(), 'ERROR', msg)
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
        msg_add(new Date(), 'ERROR', msg)
        alert(msg)
    })
} // function add_tag(item_id)

function remove_tag_link(item_id, tag_id) {
    const msg = "IMPLEMENTME: remove_tag_link(item_id, tag_id)"
    console.error(msg)
    alert(msg)
    msg_add(new Date(), 'ERROR', msg)
} // function remove_tag(item_id, tag_id)

function attach_tag_to_item(tag_id, item_id, elt_id, tag_name) {
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
        msg_add(new Date(), 'ERROR', msg)
        alert(msg)
    })
}
