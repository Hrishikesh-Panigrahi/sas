// Call the dataTables jQuery plugin

const initTable = (title) => {
  var dtb = $('#dataTable').DataTable();
  if (title == 'tt_test') {
    var days = {
      'Monday': 1,
      'Tuesday': 2,
      'Wednesday': 3,
      'Thursday': 4,
      'Friday': 5
    };
    // var dtb = $('#dataTable').DataTable({
    //   "columnDefs": [{
    //     "targets": 3,
    //     "render": function (data, type, row, meta) {
    //       if (type === 'sort') {
    //         return days[data];
    //       } else {
    //         return data;
    //       }
    //     }
    //   }]
    // });
    dtb.order([[3, 'asc'], [4, 'asc']]).draw();
  }
}
