const errTxt = $("#err")
errTxt.html("").hide();

let time_table = {
    "class": "class_id",
    "schedule": {
        "monday": [
            //{
            // "course": "course_id",
            // "teacher": "teacher_id",
            // "type": "slot_type",
            // "batch": "batch",
            // "weekday": "day"
            // "start_time": "slot_time",
            // "end_time": "slot_time",
            // },
            // Demo object
            // { course: 'Python', type: 'Lecture', batch: 'All', start_time: '09:00', end_time: '10:00' }
        ],
        "tuesday": [],
        "wednesday": [],
        "thursday": [],
        "friday": [],
        "saturday": []
    }
};

const sortByKey = (a, b) => {
    let keyA = a.start_time
    let keyB = b.start_time

    // Compare
    if (keyA < keyB) return -1;
    if (keyA > keyB) return 1;
    return 0;
}

$("#start-time").on("change", () => {
    let temp = new Date("01-01-2017 " + $("#start-time").val())
    temp.setHours(temp.getHours() + 1)
    temp = temp.toTimeString().split(' ')[0].slice(0, 5);
    // temp = temp.slice(0, 5)
    console.log(temp);
    $("#end-time").val(temp)
})

$("#add-btn").on("click", () => {
    const course = $(".select-form").val();
    const type = $("#slot-type").val();
    const batch = $("#batch").val();
    const weekday = $("#weekday").val();
    const start_time = $("#start-time").val();
    const end_time = $("#end-time").val();

    let slot = { course, type, batch, start_time, end_time }

    if (course == "" || type == "" || batch == "" || weekday == "" || start_time == "" || end_time == "")
        errTxt.html("All fields must be populated").show();
    else {
        errTxt.html("").hide();
        time_table.schedule[weekday].push(slot);
        time_table.schedule[weekday].sort(sortByKey)
    }
})