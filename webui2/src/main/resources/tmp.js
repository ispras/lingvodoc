function watchTmp(scope) {
    //console.log("Binding watchCollection on tmp dict from js...");
    //scope.$watch("dictWatchedByMe", function (newTmp, oldTmp) {
    //    console.log("watchCollection notified that collection has changed from" + JSON.stringify(oldTmp) + "to" + JSON.stringify(newTmp))
    //}, true);
    scope.dictWatchedByMe = {
        z: {z: 0}
    };
    scope.dictWatchedByMe = {
        z: {z: 10}, x: {}
    }
}

function updateTmp(scope) {
  scope.dictWatchedByMe['z']['z'] = 8
}

//{
//    tiers1 = {'t1': new TierJS({'a1': new AnnotationJS('грузите', 0, 0, 0), 'a2': new AnnotationJS('парадом', 0, 0, 0)}),
//        't2': new TierJS({'a10': new AnnotationJS('бочка', 0, 0, 0)})
//    };
//    tiers11 = {'t1': new TierJS({'a1': new AnnotationJS('грузите', 0, 0, 0), 'a2': new AnnotationJS('парадом', 0, 0, 0)}),
//        't2': new TierJS({'a10': new AnnotationJS('бочка', 0, 0, 0)})
//    };
//    tiers2 = {'t1': new TierJS({'a1': new AnnotationJS('грузите', 0, 0, 0), 'a2': new AnnotationJS('парадом', 0, 0, 0)}),
//        't2': new TierJS({'a10': new AnnotationJS('бочка', 0, 0, 0)})}
//}

// example:
elanDoc = {
    'numberOfTiers': 1,
    'tiers': {
      't1': {
          'ID': '...->t1',
          'index': 1,
          'timeAlignable': true,
          'annotations': {
              'a1': {
                  'text': 'грузите',
                  'startOffset': 250.0,
                  'durationOffset': 50.0,
                  'endOffset': 300
              },
              'a2': {
                  'text': 'бочки',
                  'startOffset': 300.0,
                  'durationOffset': 50.0,
                  'endOffset': 350.0
              }
          }
      }
    }
};